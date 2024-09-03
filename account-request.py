import boto3
import botocore.exceptions
import re
import csv
import json

def stepfunction_execution(event):
    # Create a Step Functions client
    stepfunctions = boto3.client('stepfunctions')
    
   
    
    # Start the execution of the Step Functions state machine
    response = stepfunctions.start_execution(
        stateMachineArn='arn',
        input=json.dumps(event)
        
    )
    # Return a response, if necessary
    return {
        'statusCode': 200,
        'body': 'Step Function Execution Started'
    }

def get_latest_commit_id(codecommit, repository_name, branch_name):
    try:
        response = codecommit.get_branch(repositoryName=repository_name, branchName=branch_name)
        return response['branch']['commitId']
    except botocore.exceptions.ClientError as e:
        print("Error while fetching latest commit ID:", e)
        raise

def lambda_handler(event, context):
    
    
    
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
                if len(line) > 2:
                    key, value = line[0].strip(), line[1].strip()
                    data_dict[key] = value
            
            # Retrieve the values from the dictionary
            # OU_Name = data_dict.get('OUName')
            # parent_id = data_dict.get('parentID')
            
            account_email = data_dict.get('AccountEmail')
            accountName = data_dict.get('AccountName')
            ManagedOrganizationalUnit = data_dict.get('ManagedOrganizationalUnit')
            SSOUserEmail = data_dict.get('SSOUserEmail')
            SSOUserFirstName = data_dict.get('SSOUserFirstName')
            SSOUserLastName = data_dict.get('SSOUserLastName')
            Account_Owner = data_dict.get('Account_Owner')
            change_requested_by = data_dict.get('change_requested_by')
            change_reason = data_dict.get('change_reason')
            
            
            
            # Initialize S3 and CodeCommit clients
            s3 = boto3.client('s3')
            codecommit = boto3.client('codecommit')
        
            # S3 bucket and object details
            bucket_name = 's3-terraform-scripts'
            object_key = 'account-request.tf'  # Update with the actual file path
            
            
            
            
            # Specify the desired target file name and folder path
            target_folder_path = 'terraform'  # Specify the target folder path within the repository
            target_file_name = accountName+".tf"
            print(target_file_name)
        
        
            try:
                # Download the Terraform configuration file from S3
                response = s3.get_object(Bucket=bucket_name, Key=object_key)
                file_content = response['Body'].read().decode('utf-8')
                

                # Modify the configuration data as needed using regular expressions
                
                replacements = {
                    r'AccountEmail\s+=\s+".*?"': f'AccountEmail = "{account_email}"',
                    r'AccountName\s+=\s+".*?"': f'AccountName = "{accountName}"',
                    r'ManagedOrganizationalUnit\s+=\s+".*?"': f'ManagedOrganizationalUnit = "{ManagedOrganizationalUnit}"',
                    r'SSOUserEmail\s+=\s+".*?"': f'SSOUserEmail = "{SSOUserEmail}"',
                    r'SSOUserFirstName\s+=\s+".*?"': f'SSOUserFirstName = "{SSOUserFirstName}"',
                    r'SSOUserLastName\s+=\s+".*?"': f'SSOUserLastName = "{SSOUserLastName}"',
                    
                    r'"Account:Owner"\s+=\s+".*?"': f'"Account:Owner" = "{Account_Owner}"',
                    
                    r'change_requested_by\s+=\s+".*?"': f'change_requested_by = "{change_requested_by}"',
                    r'change_reason\s+=\s+".*?"': f'change_reason = "{change_reason}"',
                    r'module "sandbox_account_3"': f'module "{accountName}"',
                }
                
                
                
        
                for old_pattern, new_value in replacements.items():
                    file_content = re.sub(old_pattern, new_value, file_content)
                
                # print("new file created”, file_content)
        
                #Specify the target file path including the folder path
                target_file_path = f'{target_folder_path}/{target_file_name}'
        
                # Fetch the latest commit ID for the branch
                repository_name = 'aft-account-request'  # Replace with your repository name
                branch_name = 'main'  # Replace with your branch name
                parent_commit_id = get_latest_commit_id(codecommit, repository_name, branch_name)
        
                # Commit the modified file to CodeCommit with the specified target file path
                codecommit_response = codecommit.put_file(
                    repositoryName=repository_name,
                    branchName=branch_name,
                    fileContent=file_content,
                    filePath=target_file_path,
                    fileMode='NORMAL',
                    parentCommitId=parent_commit_id
                )
                print("File updated and committed successfully:", codecommit_response)
                
                stepfunction_execution(event)
        
            except botocore.exceptions.ClientError as e:
                print("Error:", e)
                raise
        except Exception as e:
            print("An exception occurred:", str(e))