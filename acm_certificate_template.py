import os
from dotenv import load_dotenv
from troposphere import Template, Ref, Output, Export, certificatemanager

# Load environment variables from .env
load_dotenv()
domain_name = os.getenv("DOMAIN_NAME")
hosted_zone_id = os.getenv("HOSTED_ZONE_ID")

# Sanitize domain name
sanitized_domain = domain_name.replace(".", "-").replace("/", "-")

# Initialize the CloudFormation template
template = Template()
template.set_description("CloudFormation stack to generate ACM Certificate.")

# Define the SSL certificate for CloudFront using ACM
certificate = template.add_resource(
    certificatemanager.Certificate(
        "PortfolioCertificate",
        DomainName=domain_name,
        SubjectAlternativeNames=[f"www.{domain_name}"],
        ValidationMethod="DNS",
        DomainValidationOptions=[
            certificatemanager.DomainValidationOption(
                DomainName=domain_name,
                HostedZoneId=hosted_zone_id,
            ),
            certificatemanager.DomainValidationOption(
                DomainName=f"www.{domain_name}",
                HostedZoneId=hosted_zone_id,
            ),
        ],
    )
)

# Output the Certificate ARN for cross-stack reference
template.add_output(
    Output(
        "CertificateArn",
        Value=Ref(certificate),
        Export=Export(
            f"PortfolioCertificateARN-{sanitized_domain}"
        ),  # Name for cross-stack export
    )
)

# Write the template to a YAML file
with open(f"acm-certificate-stack-{sanitized_domain}.yaml", "w") as f:
    f.write(template.to_yaml())

print(
    f"Generated CloudFormation template: acm-certificate-stack-{sanitized_domain}.yaml"
)
