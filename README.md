# Instructions

This setup uses **Troposphere** and **Stacker** to create **CloudFormation** stacks to automatically create the AWS resources needed to deploy a functional website using **S3**, **CloudFront**, and **AWS Certificate Manager (ACM)**.

You must acquire a domain name and create a Hosted Zone manually before to proceeding.

_Note: This assumes you have the `aws cli` installed. You might have to make an **AWS Access Key** in your AWS account._

## 1. Ensure you are using the correct AWS credentials

Run `aws configure` and enter the following:

- AWS Access Key ID
- AWS Secret Access Key
- Default region name
- Default output format

## 2. Install dependencies

Run `pip install troposphere boto3 python-dotenv`

## 3. Modify .env

Enter your **Domain Name** and **Hosted zone ID** in the .env file

## 4. Run build commands in order

1. `py acm_certificate_template.py`
2. `py portfolio_website_template.py`
3. `py deploy_stack --region AWS_REGION`
   - Note: Choose preferred AWS region. Defaults to us-west-2 if not using region argument.
