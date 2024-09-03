import boto3
import subprocess
import json
import os
import urllib.request
import zipfile
import csv
import io
import re
from subprocess import call

TERRAFORM_VERSION = '1.5.6'
TERRAFORM_DOWNLOAD_URL = f'https://releases.hashicorp.com/terraform/{TERRAFORM_VERSION}/terraform_{TERRAFORM_VERSION}_linux_amd64.zip'
TERRAFORM_DIR = os.path.join('/tmp', f'terraform_{TERRAFORM_VERSION}')
TERRAFORM_PATH = os.path.join(TERRAFORM_DIR, 'terraform')

# Define the ARN of the IAM role in the target account
TARGET_ACCOUNT_ROLE_ARN = 'role-arn'

def get_account_id_by_name(account_name, role_arn):
    try:
        # Create a session using temporary credentials
        session = boto3.Session(
            aws_access_key_id=role_arn['AccessKeyId'],
            aws_secret_access_key=role_arn['SecretAccessKey'],
            aws_session_token=role_arn['SessionToken']
        )
        
        # Initialize the AWS Organizations client in the target account
        org_client = session.client('organizations')
        
        # List all AWS accounts in the organization
        response = org_client.list_accounts()
        
        # Find the account with the specified name
        for account in response['Accounts']:
            if account['Name'] == account_name:
                return account['Id']
        
        # If no matching account is found, return None
        return None

    except Exception as e:
        # Handle any exceptions that may occur during the API call
        print(f"An error occurred: {str(e)}")
        return None



def install_terraform():
    if os.path.exists(TERRAFORM_PATH):
        return

    zip_path = '/tmp/terraform.zip'
    urllib.request.urlretrieve(TERRAFORM_DOWNLOAD_URL, zip_path)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(TERRAFORM_DIR)

    terraform_binary_path = os.path.join(TERRAFORM_DIR, 'terraform')
    os.chmod(terraform_binary_path, 0o755)  # Set executable permissions

def assume_role_and_run_terraform(event):
    # Create an STS client
    sts_client = boto3.client('sts')

    # Assume the IAM role in the target account
    assumed_role = sts_client.assume_role(
        RoleArn=TARGET_ACCOUNT_ROLE_ARN,
        RoleSessionName='AssumedRoleSession'
    )

    # Get temporary credentials
    aws_access_key_id = assumed_role['Credentials']['AccessKeyId']
    aws_secret_access_key = assumed_role['Credentials']['SecretAccessKey']
    aws_session_token = assumed_role['Credentials']['SessionToken']

    # Set the temporary credentials as environment variables
    os.environ['AWS_ACCESS_KEY_ID'] = aws_access_key_id
    os.environ['AWS_SECRET_ACCESS_KEY'] = aws_secret_access_key
    os.environ['AWS_SESSION_TOKEN'] = aws_session_token

    # Rest of your code remains unchanged
    install_terraform()
    s3 = boto3.client('s3')
    
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']
    
    
    # Check if the file is a CSV
    if key.endswith('.csv'):
        try:
            # Fetch the CSV file from S3
            response = s3.get_object(Bucket=bucket, Key=key)
            
            # Read the CSV file content
            csv_content = response['Body'].read().decode('utf-8')
            
            
            # Split the CSV content by lines
            lines = csv.reader(csv_content.splitlines())
        
            # Initialize an empty dictionary to store the data
            data_dict = {}
            
            for line in lines:
                if len(line) >= 2:
                    key, value = line[0].strip(), line[1].strip()
                    data_dict[key] = value
            
            # Retrieve the values from the dictionary
            
            AccountName = data_dict.get('AccountName')
            cw_event_rule_name = data_dict.get('cw_event_rule_name')
            cw_event_rule_description = data_dict.get('cw_event_rule_description')
            sns_topic_name = data_dict.get('sns_topic_name')
            sns_display_name = data_dict.get('sns_display_name')
            sns_topic_sub_endpoint = data_dict.get('sns_topic_sub_endpoint')
            
            
            try:
                # Replace with your target AWS account ID and role ARN
                target_account_id = 'account-id'
                target_role_arn = 'role-arn'
    
                
                account_name = AccountName
                
                # Assume the role in the target account
                sts_client = boto3.client('sts')
                assumed_role = sts_client.assume_role(
                    RoleArn=target_role_arn,
                    RoleSessionName='LambdaSession'
                )
        
                # Get the account ID based on the account name
                account_id = get_account_id_by_name(account_name, assumed_role['Credentials'])
                
    
                
                if account_id:
                    
                    response = {
                         'statusCode': 200,
                         'body': f'Account ID for {account_name}: {account_id}'
                }
                else:
                    response = {
                        'statusCode': 404,
                        'body': f'Account with name {account_name} not found'
            }
            
            
            except Exception as e:
                response = {
                        'statusCode': 500,
                        'body': f'An error occurred: {str(e)}'
                }
                print(response['body'])
            
            
            cw_event_rule_accountid = str(account_id)
           
            
            
            
            response = s3.get_object(Bucket="s3-terraform-scripts", Key="eventbridge.tf")
            terraform_script_content = response['Body'].read().decode('utf-8')
        
            # Modify the Terraform script content
            # Modify the configuration data as needed using regular expressions
                
            
            replacements = {
                r'cw_event_rule_name\s+=\s+".*?"': f'cw_event_rule_name = "{cw_event_rule_name}"',
                r'cw_event_rule_description\s+=\s+".*?"': f'cw_event_rule_description = "{cw_event_rule_description}"',
                r'cw_event_rule_accountid\s+=\s+".*?"': f'cw_event_rule_accountid = "{cw_event_rule_accountid}"',
                r'sns_topic_name\s+=\s+".*?"': f'sns_topic_name = "{sns_topic_name}"',
                r'sns_display_name\s+=\s+".*?"': f'sns_display_name = "{sns_display_name}"',
                r'sns_topic_sub_endpoint\s+=\s+".*?"': f'sns_topic_sub_endpoint = "{sns_topic_sub_endpoint}"',
            }

            for old_pattern, new_value in replacements.items():
                terraform_script_content = re.sub(old_pattern, new_value, terraform_script_content)
            
            main_tf_path = os.path.join(TERRAFORM_DIR, 'main.tf')
            with open(main_tf_path, 'w') as tf_file:
                tf_file.write(terraform_script_content)

            # Debug: Print the content of the written main.tf
            with open(main_tf_path, 'r') as tf_file:
                written_content = tf_file.read()
                
            # Initialize Terraform (terraform init)
            init_command = [TERRAFORM_PATH, "init -upgrade"]
            print("Working directory:", TERRAFORM_DIR)
            init_process = subprocess.Popen(init_command, cwd=TERRAFORM_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            init_stdout, init_stderr = init_process.communicate()
        
            # # Debug: Print the output of terraform init
            # print("Terraform init stdout:", init_stdout)
            # print("Terraform init stderr:", init_stderr)
            
            # Run terraform plan
            plan_command = [TERRAFORM_PATH, "plan"]
            print("Working directory:", TERRAFORM_DIR)
            plan_process = subprocess.Popen(plan_command, cwd=TERRAFORM_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            plan_stdout, plan_stderr = plan_process.communicate()
            
            # Debug: Print the output of terraform plan
            print("Terraform plan stdout:", plan_stdout)
            print("Terraform plan stderr:", plan_stderr)
         
         
         
            # Apply Terraform changes (terraform apply)
            apply_command = [TERRAFORM_PATH, "apply", "-auto-approve"]
            apply_process = subprocess.Popen(apply_command, cwd=TERRAFORM_DIR, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            apply_stdout, apply_stderr = apply_process.communicate(input=terraform_script_content)
            
             # Debug: Print the output of terraform apply
            print("Terraform apply stdout:", apply_stdout)
            print("Terraform apply stderr:", apply_stderr)
        
            if apply_process.returncode == 0:
                return {"statusCode": 200}
            else:
                error_message = f"Terraform command failed during apply:\n{apply_stderr}"
                return {"statusCode": 500, "body": error_message}
            
        except Exception as e:
            print("An exception occurred:", str(e))
    else:
        print("File is not a CSV.")
   

def lambda_handler(event, context):
    print(event)
    try:
        call('rm -rf /tmp/*', shell=True)
        assume_role_and_run_terraform(event)
        return {"statusCode": 200}
    except Exception as e:
        print(f"An exception occurred: {str(e)}")
        return {"statusCode": 500, "body": str(e)}
