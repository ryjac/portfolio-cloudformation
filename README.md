# Instructions

This setup uses **Troposphere** and **Boto3** to deploy **CloudFormation** stacks which automatically provision the AWS resources needed to create a functional portfolio website using **S3**, **CloudFront**, **AWS Certificate Manager (ACM)**, and **Route53**. It also creates an automated CI/CD pipeline using **AWS CodeBuild** and **AWS CodePipeline** which will automatically redeploy your website every time you push changes to your GitHub repo, and invalidates **CloudFront** cache to display changes immediately.

Use your own website files, or clone my portfolio template from https://github.com/ryjac/portfolio.

_Note: This assumes you have `aws cli` installed._

**You must acquire a domain and create a Hosted Zone manually in AWS before proceeding.**

## 1. Install dependencies

Run `pip install troposphere boto3 python-dotenv`

## 2. Modify .env

Open the `.env` file and enter your:

- `DOMAIN_NAME` _e.g., **example.com**_
- `HOSTED_ZONE_ID` _e.g., **Z04705991OWH0GEXAMPLE**_
- `GITHUB_USER_NAME` _Your github username. e.g., **ryjac**_
- `GITHUB_REPO_NAME` _The repo you will host your website files. e.g., if it is **github.com/ryjac/portfolio** you would enter **portfolio**_
- `GITHUB_APP_CONNECTION_ARN` _e.g., **arn:aws:codeconnections:us-west-2:AWS_ACCOUNT_NUMBER:connection/CONNECTION_ID**_

## 3. Build the CloudFormation templates

1. `py acm_certificate_template.py`
2. `py portfolio_website_template.py`
3. `py cicd_pipeline_template.py`

## 4. Deploy the CloudFormation stacks

- `py deploy_stacks --region AWS_REGION`
  - Note: Use the `--region` option with your preferred `AWS_REGION` as the argument to specify deployment region for the main stacks. Defaults to `us-west-2` if `--region` is not provided.
