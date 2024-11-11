import os
from dotenv import load_dotenv
from troposphere import (
    Template,
    Ref,
    Sub,
    Parameter,
    GetAtt,
    s3,
    cloudfront,
    route53,
)

# Load environment variables from .env
load_dotenv()
domain_name = os.getenv("DOMAIN_NAME")
hosted_zone_id = os.getenv("HOSTED_ZONE_ID")

# Initialize the CloudFormation template
template = Template()
template.set_description(
    "Infrastructure for hosting a portfolio website using CloudFormation."
)

# Add region as a parameter
region_param = template.add_parameter(
    Parameter(
        "DeploymentRegion",
        Type="String",
        Description="AWS region for deployment",
    )
)

# Retrieve the ACM certificate ARN
certificate_arn_param = template.add_parameter(
    Parameter(
        "CertificateArn",
        Type="String",
        Description="The ARN of the ACM certificate in us-east-1",
    )
)

# Define S3 bucket for website hosting
root_bucket = template.add_resource(
    s3.Bucket(
        "PortfolioRootBucket",
        BucketName=domain_name,
        WebsiteConfiguration=s3.WebsiteConfiguration(
            IndexDocument="index.html", ErrorDocument="error.html"
        ),
        PublicAccessBlockConfiguration=s3.PublicAccessBlockConfiguration(
            BlockPublicAcls=False,
            IgnorePublicAcls=False,
            BlockPublicPolicy=False,
            RestrictPublicBuckets=False,
        ),
    )
)


# Define S3 bucket for www-redirect
redirect_bucket = template.add_resource(
    s3.Bucket(
        "PortfolioRedirectBucket",
        BucketName=f"www.{domain_name}",
        WebsiteConfiguration=s3.WebsiteConfiguration(
            RedirectAllRequestsTo=s3.RedirectAllRequestsTo(
                HostName=domain_name,
                Protocol="http",
            )
        ),
        PublicAccessBlockConfiguration=s3.PublicAccessBlockConfiguration(
            BlockPublicAcls=False,
            IgnorePublicAcls=False,
            BlockPublicPolicy=False,
            RestrictPublicBuckets=False,
        ),
    )
)

# Define the 'root' CloudFront distribution
root_distribution = template.add_resource(
    cloudfront.Distribution(
        "PortfolioRootDistribution",
        DependsOn="PortfolioRootBucket",  # Ensure the bucket is created first
        DistributionConfig=cloudfront.DistributionConfig(
            Origins=[
                cloudfront.Origin(
                    Id="S3-Portfolio-Root",
                    DomainName=Sub(
                        "${DomainName}.s3-website-${DeploymentRegion}.amazonaws.com",
                        {
                            "DomainName": domain_name,
                            "DeploymentRegion": Ref(region_param),
                        },
                    ),
                    CustomOriginConfig=cloudfront.CustomOriginConfig(
                        OriginProtocolPolicy="http-only"
                    ),
                )
            ],
            Enabled=True,
            Comment="'Root' distribution",
            Aliases=[domain_name],
            ViewerCertificate=cloudfront.ViewerCertificate(
                AcmCertificateArn=Ref(certificate_arn_param),
                SslSupportMethod="sni-only",
                MinimumProtocolVersion="TLSv1.2_2021",
            ),
            DefaultCacheBehavior=cloudfront.DefaultCacheBehavior(
                TargetOriginId="S3-Portfolio-Root",
                ViewerProtocolPolicy="redirect-to-https",
                AllowedMethods=["GET", "HEAD"],
                CachedMethods=["GET", "HEAD"],
                ForwardedValues=cloudfront.ForwardedValues(
                    QueryString=False,
                    Cookies=cloudfront.Cookies(Forward="none"),
                ),
                CachePolicyId="658327ea-f89d-4fab-a63d-7e88639e58f6",  # Managed-CachingOptimized
            ),
            PriceClass="PriceClass_All",
            HttpVersion="http3",
        ),
    )
)

# Define the 'redirect' CloudFront distribution
redirect_distribution = template.add_resource(
    cloudfront.Distribution(
        "PortfolioRedirectDistribution",
        DependsOn="PortfolioRedirectBucket",  # Ensure the bucket is created first
        DistributionConfig=cloudfront.DistributionConfig(
            Origins=[
                cloudfront.Origin(
                    Id="S3-Portfolio-Redirect",
                    DomainName=Sub(
                        "www.${DomainName}.s3-website-${DeploymentRegion}.amazonaws.com",
                        {
                            "DomainName": domain_name,
                            "DeploymentRegion": Ref(region_param),
                        },
                    ),
                    CustomOriginConfig=cloudfront.CustomOriginConfig(
                        OriginProtocolPolicy="http-only"
                    ),
                )
            ],
            Enabled=True,
            Comment="'Redirect' distribution",
            Aliases=[f"www.{domain_name}"],
            ViewerCertificate=cloudfront.ViewerCertificate(
                AcmCertificateArn=Ref(certificate_arn_param),
                SslSupportMethod="sni-only",
                MinimumProtocolVersion="TLSv1.2_2021",
            ),
            DefaultCacheBehavior=cloudfront.DefaultCacheBehavior(
                TargetOriginId="S3-Portfolio-Redirect",
                ViewerProtocolPolicy="redirect-to-https",
                AllowedMethods=["GET", "HEAD"],
                CachedMethods=["GET", "HEAD"],
                ForwardedValues=cloudfront.ForwardedValues(
                    QueryString=False,
                    Cookies=cloudfront.Cookies(Forward="none"),
                ),
                CachePolicyId="658327ea-f89d-4fab-a63d-7e88639e58f6",  # Managed-CachingOptimized
            ),
            PriceClass="PriceClass_All",
            HttpVersion="http3",
        ),
    )
)

# Define root S3 bucket policy, using the DistributionId from CloudFront
bucket_policy = template.add_resource(
    s3.BucketPolicy(
        "PortfolioRootBucketPolicy",
        DependsOn=[
            "PortfolioRootDistribution",
            "PortfolioRootBucket",
        ],  # Ensure the 'root' bucket and distribution are created first
        Bucket=Ref(root_bucket),
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicReadForWebsiteAccess",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{domain_name}/*",
                },
                {
                    "Sid": "CloudFrontDistributionReadAccess",
                    "Effect": "Allow",
                    "Principal": {"Service": "cloudfront.amazonaws.com"},
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{domain_name}/*",
                    "Condition": {
                        "StringEquals": {
                            "AWS:SourceArn": Sub(
                                "arn:aws:cloudfront::${AWS::AccountId}:distribution/${DistributionId}",
                                {"DistributionId": Ref(root_distribution)},
                            )
                        }
                    },
                },
            ],
        },
    )
)

# Route 53 A Record to point primary domain to the 'root' CloudFront distribution
a_record_root = template.add_resource(
    route53.RecordSetType(
        "PortfolioRootDNSRecord",
        HostedZoneId=hosted_zone_id,
        Name=domain_name,
        Type="A",
        AliasTarget=route53.AliasTarget(
            DNSName=GetAtt(root_distribution, "DomainName"),
            HostedZoneId="Z2FDTNDATAQYW2",  # AWS Global CloudFront Hosted Zone ID (don't change this)
        ),
    )
)

# Route 53 A Record to point www-prefixed domain to the 'redirect' CloudFront distribution
a_record_redirect = template.add_resource(
    route53.RecordSetType(
        "PortfolioRedirectDNSRecord",
        HostedZoneId=hosted_zone_id,
        Name=f"www.{domain_name}",
        Type="A",
        AliasTarget=route53.AliasTarget(
            DNSName=GetAtt(redirect_distribution, "DomainName"),
            HostedZoneId="Z2FDTNDATAQYW2",  # AWS Global CloudFront Hosted Zone ID (don't change this)
        ),
    )
)

# Export the CloudFormation template as YAML
with open("portfolio-website-stack.yaml", "w") as f:
    f.write(template.to_yaml())

print("Generated CloudFormation template: portfolio-website-stack.yaml")
