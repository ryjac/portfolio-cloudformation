import boto3
import time
import argparse

# Stack names and template files
MAIN_STACK_NAME = "portfolio-website-stack"
MAIN_TEMPLATE_FILE = "portfolio-website-stack.yaml"
ACM_STACK_NAME = "acm-certificate-stack"
ACM_TEMPLATE_FILE = "acm-certificate-stack.yaml"

# List of valid AWS regions (as of 11/09/2024)
VALID_AWS_REGIONS = [
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
    "af-south-1",
    "ap-east-1",
    "ap-south-1",
    "ap-northeast-1",
    "ap-northeast-2",
    "ap-northeast-3",
    "ap-southeast-1",
    "ap-southeast-2",
    "ca-central-1",
    "cn-north-1",
    "cn-northwest-1",
    "eu-central-1",
    "eu-west-1",
    "eu-west-2",
    "eu-west-3",
    "eu-north-1",
    "eu-south-1",
    "me-south-1",
    "sa-east-1",
]

# Regions
MAIN_REGION = "us-west-2"  # Default region for the main stack
ACM_REGION = "us-east-1"  # Required region for ACM certificate

# Parse command-line arguments for --region argument (default to MAIN_REGION)
parser = argparse.ArgumentParser(
    description="Deploy a CloudFormation stack.",
)
parser.add_argument(
    "--region",
    default=MAIN_REGION,
    choices=VALID_AWS_REGIONS,
    help=f"The AWS region to deploy the main stack in (default: {MAIN_REGION})",
)
args = parser.parse_args()

MAIN_REGION = args.region  # overrides default region if user provides --region argument

# Initialize the CloudFormation clients
cf_client_main = boto3.client("cloudformation", region_name=MAIN_REGION)
cf_client_acm = boto3.client("cloudformation", region_name=ACM_REGION)


# Load a template file
def load_template(template_file):
    with open(template_file, "r") as f:
        return f.read()


# Deploy a stack with the given client, name, and template
def deploy_stack(client, stack_name, template_body, parameters=[], region=""):
    try:
        # Check if stack exists and its status
        response = client.describe_stacks(StackName=stack_name)
        stack_status = response["Stacks"][0]["StackStatus"]

        # If the stack is in a failed or rollback state, delete it before re-creating
        if stack_status in ["ROLLBACK_COMPLETE", "DELETE_FAILED"]:
            print(
                f"Stack {stack_name} has status: {stack_status}. Deleting it for a fresh deployment."
            )
            client.delete_stack(StackName=stack_name)
            wait_for_stack_deletion(client, stack_name)

        # If stack exists and is in a valid state, proceed with an update
        client.update_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Parameters=parameters,
            Capabilities=["CAPABILITY_NAMED_IAM"],
        )
        print(f"Stack {stack_name} update initiated in region {region}.")

    except client.exceptions.ClientError as e:
        # Creates new stack if it doesn't exist
        if "does not exist" in str(e):
            print(f"Stack {stack_name} does not exist. Creating a new stack.")
            client.create_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Parameters=parameters,
                Capabilities=["CAPABILITY_NAMED_IAM"],
            )
            print(f"Stack {stack_name} creation initiated in region {region}.")
        elif "No updates are to be performed" in str(e):
            print(f"No updates to be performed for {stack_name} in region {region}.")
        else:
            raise e

    wait_for_stack(client, stack_name)


# Monitor stack operation status
def wait_for_stack(client, stack_name):
    while True:
        try:
            response = client.describe_stacks(StackName=stack_name)
            stack_status = response["Stacks"][0]["StackStatus"]
            print(f"Current stack status of {stack_name}: {stack_status}")

            if stack_status in [
                "CREATE_COMPLETE",
                "UPDATE_COMPLETE",
                "DELETE_COMPLETE",
            ]:
                print(f"Stack {stack_name} operation successful.")
                break
            elif stack_status.endswith("FAILED"):
                print(
                    f"Stack {stack_name} operation failed with status: {stack_status}"
                )
                break
            elif stack_status == "ROLLBACK_COMPLETE":
                print(f"Stack {stack_name} rolled back successfully.")
                break
        except client.exceptions.ClientError as e:
            if "does not exist" in str(e):
                print(f"Stack {stack_name} successfully deleted.")
                break
            else:
                raise e

        time.sleep(10)


# Delete stack
def wait_for_stack_deletion(client, stack_name):
    while True:
        try:
            client.describe_stacks(StackName=stack_name)
            print(f"Waiting for {stack_name} deletion to complete...")
            time.sleep(10)
        except client.exceptions.ClientError as e:
            if "does not exist" in str(e):
                print(f"Stack {stack_name} successfully deleted.")
                break
            else:
                raise e


# Main deployment flow
def main():
    # Step 1: Deploy the ACM stack in us-east-1
    acm_template_body = load_template(ACM_TEMPLATE_FILE)
    deploy_stack(cf_client_acm, ACM_STACK_NAME, acm_template_body, region=ACM_REGION)

    # Step 2: Retrieve the CertificateArn after ACM stack deployment
    try:
        certificate_arn = cf_client_acm.describe_stacks(StackName=ACM_STACK_NAME)[
            "Stacks"
        ][0]["Outputs"][0]["OutputValue"]
        print(f"Retrieved Certificate ARN: {certificate_arn}")
    except (IndexError, KeyError):
        print("Error: Could not retrieve CertificateArn from ACM stack.")
        return

    # Step 3: Deploy the main stack in specified region with the ACM certificate ARN
    main_template_body = load_template(MAIN_TEMPLATE_FILE)
    deploy_stack(
        cf_client_main,
        MAIN_STACK_NAME,
        main_template_body,
        parameters=[
            {"ParameterKey": "CertificateArn", "ParameterValue": certificate_arn},
            {"ParameterKey": "DeploymentRegion", "ParameterValue": MAIN_REGION},
        ],
        region=MAIN_REGION,
    )


if __name__ == "__main__":
    main()
