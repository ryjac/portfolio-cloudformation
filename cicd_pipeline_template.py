import os
from dotenv import load_dotenv
from troposphere import (
    Template,
    Ref,
    Join,
    GetAtt,
    Parameter,
    iam,
    codebuild,
    codepipeline,
    s3,
)

# Load environment variables from .env
load_dotenv()
domain_name = os.getenv("DOMAIN_NAME")
github_user_name = os.getenv("GITHUB_USER_NAME")
github_repo_name = os.getenv("GITHUB_REPO_NAME")
github_app_connection_arn = os.getenv("GITHUB_APP_CONNECTION_ARN")

# Sanitize domain name
sanitized_domain = domain_name.replace(".", "-").replace("/", "-")

# Initialize the CloudFormation template
template = Template()
template.set_description(
    "CloudFormation stack for creating CI/CD pipeline with CodeBuild and CodePipeline."
)

# Retrieve the 'root' CloudFront Distribution ID
distribution_id_param = template.add_parameter(
    Parameter(
        "DistributionId",
        Type="String",
        Description="The Distribution ID of the 'root' CloudFront distribution.",
    )
)

# Retrieve the 'root' S3 Bucket name
root_bucket_name_param = template.add_parameter(
    Parameter(
        "RootBucketName",
        Type="String",
        Description="The name of the 'root' S3 Bucket.",
    )
)

# Define the S3 bucket for CodePipeline artifacts
artifact_bucket = template.add_resource(s3.Bucket("PipelineArtifactBucket"))

# Define IAM Role for CodeBuild with necessary permissions for CloudFront invalidations
codebuild_role = template.add_resource(
    iam.Role(
        "CodeBuildServiceRole",
        AssumeRolePolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": [
                            "codebuild.amazonaws.com",
                        ]
                    },
                    "Action": "sts:AssumeRole",
                }
            ],
        },
        Policies=[
            iam.Policy(
                PolicyName=f"CodeBuildPolicy-{sanitized_domain}",
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": [
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                            ],
                            "Resource": [
                                Join(
                                    "",
                                    [
                                        "arn:aws:logs:",
                                        Ref("AWS::Region"),
                                        ":",
                                        Ref("AWS::AccountId"),
                                        ":log-group:/aws/codebuild/Build-GitHubPortfolio*",
                                    ],
                                ),  # CloudWatch Logs for CodeBuild
                            ],
                        },
                        {
                            "Effect": "Allow",
                            "Action": [
                                "cloudfront:CreateInvalidation",
                            ],
                            "Resource": [
                                Join(
                                    "",
                                    [
                                        "arn:aws:cloudfront::",
                                        Ref("AWS::AccountId"),
                                        ":distribution/",
                                        Ref(distribution_id_param),
                                    ],
                                ),  # 'root' CloudFront distribution ARN for invalidations
                            ],
                        },
                        {
                            "Effect": "Allow",
                            "Action": [
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:GetBucketLocation",
                            ],
                            "Resource": [
                                Join(
                                    "", ["arn:aws:s3:::", Ref(artifact_bucket)]
                                ),  # artifact S3 bucket
                                Join(
                                    "", ["arn:aws:s3:::", Ref(artifact_bucket), "/*"]
                                ),  # Objects in artifact S3 bucket
                            ],
                        },
                        {
                            "Effect": "Allow",
                            "Action": [
                                "codestar-connections:UseConnection",
                                "codebuild:BatchGetBuilds",
                                "codebuild:StartBuild",
                                "codebuild:StopBuild",
                                "codebuild:ListBuilds",
                            ],
                            "Resource": [
                                github_app_connection_arn,
                            ],
                        },
                    ],
                },
            )
        ],
    )
)

# Define buildspec file (configured for next.js)
buildspec = """
    version: 0.2
    phases:
        install:
            commands:
                - npm install
        build:
            commands:
                - npm run build

        post_build:
            commands:
                - aws cloudfront create-invalidation --distribution-id $DISTRIBUTION_ID --paths "/*"
    artifacts:
        files:
            - "**/*"
        base-directory: out

    cache:
        paths:
            - "node_modules/**/*" # Cache `node_modules` for faster `yarn` or `npm i`
            - ".next/cache/**/*" # Cache Next.js for faster application rebuilds
"""

# Create CodeBuild Project
codebuild_project = template.add_resource(
    codebuild.Project(
        "CodeBuildGitHubPortfolio",
        Name=f"Build-GitHubPortfolio-{sanitized_domain}",
        Source=codebuild.Source(
            Type="GITHUB",
            Location=f"https://github.com/{github_user_name}/{github_repo_name}",
            GitCloneDepth=1,
            ReportBuildStatus=True,
            BuildSpec=buildspec,
        ),
        Environment=codebuild.Environment(
            ComputeType="BUILD_GENERAL1_SMALL",
            Image="aws/codebuild/amazonlinux2-x86_64-standard:5.0",
            Type="LINUX_CONTAINER",
            EnvironmentVariables=[
                {"Name": "DISTRIBUTION_ID", "Value": Ref(distribution_id_param)}
            ],
        ),
        ServiceRole=Ref(codebuild_role),
        Artifacts=codebuild.Artifacts(Type="NO_ARTIFACTS"),
    )
)

# Define IAM Role for CodePipeline with necessary permissions for starting CodeBuild builds
codepipeline_role = template.add_resource(
    iam.Role(
        "CodePipelineServiceRole",
        AssumeRolePolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "codepipeline.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        },
        Policies=[
            iam.Policy(
                PolicyName=f"CodePipelinePolicy-{sanitized_domain}",
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": "iam:PassRole",
                            "Resource": "*",
                            "Condition": {
                                "StringEqualsIfExists": {
                                    "iam:PassedToService": [
                                        "codebuild.amazonaws.com",
                                        "cloudformation.amazonaws.com",
                                    ]
                                }
                            },
                        },
                        {
                            "Effect": "Allow",
                            "Action": [
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:PutObjectAcl",
                                "s3:PutObjectVersionAcl",
                                "s3:GetBucketLocation",
                                "s3:ListBucket",
                            ],
                            "Resource": [
                                Join(
                                    "", ["arn:aws:s3:::", Ref(artifact_bucket)]
                                ),  # artifact S3 bucket
                                Join(
                                    "", ["arn:aws:s3:::", Ref(artifact_bucket), "/*"]
                                ),  # Objects in artifact S3 bucket
                                Join(
                                    "", ["arn:aws:s3:::", Ref(root_bucket_name_param)]
                                ),  # 'root' S3 bucket
                                Join(
                                    "",
                                    [
                                        "arn:aws:s3:::",
                                        Ref(root_bucket_name_param),
                                        "/*",
                                    ],  # Objects in 'root' S3 bucket
                                ),
                            ],
                        },
                        {
                            "Effect": "Allow",
                            "Action": [
                                "codestar-connections:UseConnection",
                                "codebuild:BatchGetBuilds",
                                "codebuild:StartBuild",
                                "codebuild:StopBuild",
                                "codebuild:ListBuilds",
                            ],
                            "Resource": [
                                GetAtt(codebuild_project, "Arn"),
                                github_app_connection_arn,
                            ],
                        },
                    ],
                },
            )
        ],
    )
)

# CodePipeline Setup
pipeline = template.add_resource(
    codepipeline.Pipeline(
        "PipelineGitHubPortfolio",
        Name=f"Pipeline-GitHubPortfolio-{sanitized_domain}",
        RoleArn=GetAtt(codepipeline_role, "Arn"),
        PipelineType="V2",
        ArtifactStore=codepipeline.ArtifactStore(
            Type="S3",
            Location=Ref(artifact_bucket),
        ),
        Stages=[
            codepipeline.Stages(
                Name="Source",
                Actions=[
                    codepipeline.Actions(
                        Name="SourceAction",
                        ActionTypeId=codepipeline.ActionTypeId(
                            Category="Source",
                            Owner="AWS",
                            Provider="CodeStarSourceConnection",
                            Version="1",
                        ),
                        Configuration={
                            "ConnectionArn": github_app_connection_arn,
                            "FullRepositoryId": f"{github_user_name}/{github_repo_name}",
                            "BranchName": "main",
                        },
                        OutputArtifacts=[
                            codepipeline.OutputArtifacts(Name="SourceArtifact")
                        ],
                        RunOrder=1,
                    )
                ],
            ),
            codepipeline.Stages(
                Name="Build",
                Actions=[
                    codepipeline.Actions(
                        Name="BuildAction",
                        ActionTypeId=codepipeline.ActionTypeId(
                            Category="Build",
                            Owner="AWS",
                            Provider="CodeBuild",
                            Version="1",
                        ),
                        Configuration={"ProjectName": Ref(codebuild_project)},
                        InputArtifacts=[
                            codepipeline.InputArtifacts(Name="SourceArtifact")
                        ],
                        OutputArtifacts=[
                            codepipeline.OutputArtifacts(Name="BuildArtifact")
                        ],
                        RunOrder=1,
                    )
                ],
            ),
            codepipeline.Stages(
                Name="Deploy",
                Actions=[
                    codepipeline.Actions(
                        Name="DeployAction",
                        ActionTypeId=codepipeline.ActionTypeId(
                            Category="Deploy",
                            Owner="AWS",
                            Provider="S3",
                            Version="1",
                        ),
                        Configuration={
                            "BucketName": Ref(root_bucket_name_param),
                            "Extract": "true",
                        },
                        InputArtifacts=[
                            codepipeline.InputArtifacts(Name="BuildArtifact")
                        ],
                        RunOrder=1,
                    )
                ],
            ),
        ],
    )
)

# Export the CloudFormation template as YAML
with open(f"cicd-pipeline-stack-{sanitized_domain}.yaml", "w") as f:
    f.write(template.to_yaml())

print(f"Generated CloudFormation template: cicd-pipeline-stack-{sanitized_domain}.yaml")
