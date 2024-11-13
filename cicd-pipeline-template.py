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
github_user_name = os.getenv("GITHUB_USER_NAME")
github_repo_name = os.getenv("GITHUB_REPO_NAME")
github_app_connection_arn = os.getenv("GITHUB_APP_CONNECTION_ARN")

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
                            "codepipeline.amazonaws.com",
                        ]
                    },
                    "Action": "sts:AssumeRole",
                }
            ],
        },
        Policies=[
            iam.Policy(
                PolicyName="CodeBuildPolicy",
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": [
                                "s3:*",
                                "cloudfront:CreateInvalidation",
                                "codestar-connections:UseConnection",
                                "codebuild:StartBuild",
                            ],
                            "Resource": [
                                Join(
                                    "", ["arn:aws:s3:::", Ref(artifact_bucket)]
                                ),  # S3 artifact bucket
                                Join(
                                    "", ["arn:aws:s3:::", Ref(artifact_bucket), "/*"]
                                ),  # Objects in bucket
                                # GetAtt(
                                #     codebuild_project, "Arn"
                                # ),  ##! LEFT OFF HERE, TRYING TO GET CODEBUILD PERMISSION
                                github_app_connection_arn,
                            ],
                        }
                    ],
                },
            )
        ],
    )
)

# Create CodeBuild Project
codebuild_project = template.add_resource(
    codebuild.Project(
        "CodeBuildGitHubPortfolio",
        Name="Build-GitHubPortfolio_TEMP",
        Source=codebuild.Source(
            Type="GITHUB",
            Location=f"https://github.com/{github_user_name}/{github_repo_name}",
            GitCloneDepth=1,
            ReportBuildStatus=True,
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

# CodePipeline Setup
pipeline = template.add_resource(
    codepipeline.Pipeline(
        "PipelineGitHubPortfolio",
        Name="Pipeline-GitHubPortfolio_TEMP",
        RoleArn=GetAtt(codebuild_role, "Arn"),
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
with open("cicd-pipeline-stack.yaml", "w") as f:
    f.write(template.to_yaml())

print("Generated CloudFormation template: cicd-pipeline-stack.yaml")
