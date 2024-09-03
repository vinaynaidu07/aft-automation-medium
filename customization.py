import boto3
import botocore.exceptions
import re
import csv
import json

TARGET_ACCOUNT_ROLE_ARN = 'IAM role ARN'


def get_latest_commit_id(codecommit, repository_name, branch_name):
    try:
        response = codecommit.get_branch(repositoryName=repository_name, branchName=branch_name)
        return response['branch']['commitId']
    except botocore.exceptions.ClientError as e:
        print("Error while fetching latest commit ID:", e)
        raise
    
def custom_sort_key(file_key):
    if file_key == "terraform.tfvars":
        return (0, file_key)  # Assign a lower sort value for "account-request.tf"
    else:
        return (1, file_key)  # Assign a higher sort value for other files
        
def list_conversion(names):
    formatted_user_list = ['"' + name.strip() + '"' for name in names]
    output_string = '[' + ', '.join(formatted_user_list) + ']'
    return output_string


def extractcsv(event):
    s3 = boto3.client('s3')
    # Retrieve the bucket name and object key from the step function passed event details
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    object_key = event['Records'][0]['s3']['object']['key']

    # Initialize an empty dictionary to store key-value pairs
    key_value_dict = {}
    

    try:
        # Download the CSV file from S3
        csv_file = s3.get_object(Bucket=bucket_name, Key=object_key)
        csv_data = csv_file['Body'].read().decode('utf-8').splitlines()

        # Parse the CSV data
        for line in csv_data:
            # Split the line into columns
            columns = line.split(',')

            # Extract values from the first two columns
            if len(columns) >= 2:
                key = columns[0].strip()
                value = columns[1].strip()
                key_value_dict[key] = value

    except Exception as e:
        # Handle any exceptions that may occur while reading the file
        return {
            'statusCode': 500,
            'body': str(e)
        }
    
    # Return a response if necessary
    return key_value_dict

    
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
        
        results = response["Accounts"]
        while "NextToken" in response:
            response = org_client.list_accounts(NextToken=response["NextToken"])
            results.extend(response["Accounts"])       
        # Find the account with the specified name
        for account in results:
            print(account)
            print(account['Name'])
            print(account_name)
            if account['Name'] == account_name:
                return account['Id']
        
        # If no matching account is found, return None
        return None

    except Exception as e:
        # Handle any exceptions that may occur during the API call
        print(f"An error occurred: {str(e)}")
        return None

def commitfiles(formcontent,event):
    
    #To fetch the terraform file from s3
    bucket = "s3-terraform-scripts"
    folder = "terraform_files/"
    s3 = boto3.resource("s3")
    s3_bucket = s3.Bucket(bucket)
    files_in_s3 = [f.key[len(folder):] for f in s3_bucket.objects.filter(Prefix=folder)]
    print('files without sort' , files_in_s3)
    files_in_s3 = sorted(files_in_s3, key=custom_sort_key)
    files_in_s3 = [file_key for file_key in files_in_s3 if file_key != '']
    print('files after sort' , files_in_s3)
    
    
    repository_name = "account_customization"
    branch_name = 'main'
    
    s3 = boto3.client('s3')
    
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    # Check if the file is a CSV
    if key.endswith('.csv'):
        try:
        
        
            # Fetch the CSV file from S3
            response = s3.get_object(Bucket=bucket_name, Key=key)
            
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
            
            AccountName = data_dict.get('AccountName')
            
            SSOUserEmail = data_dict.get('SSOUserEmail')
            SSOUserFirstName = data_dict.get('SSOUserFirstName')
            SSOUserLastName = data_dict.get('SSOUserLastName')
            Group_Name = data_dict.get('Group_Name')
            description = data_dict.get('description')
            budget_name = data_dict.get('budget_name')
            Username = data_dict.get('Username')
            FirstName = data_dict.get('FirstName')
            LastName = data_dict.get('LastName') 
            Tenant_companyName = data_dict.get('Tenant_companyName')
            Tenant_email = data_dict.get('Tenant_email')
            limit_amount = data_dict.get('limit_amount')

            try:
                print('executed')
                # Replace with your target AWS account ID and role ARN
                target_account_id = 'account-id'
                target_role_arn = TARGET_ACCOUNT_ROLE_ARN
     
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
 
            AccountID = str(account_id)
            cw_event_rule_accountid = AccountID
            cw_event_rule_name = data_dict.get('cw_event_rule_name')
            cw_event_rule_description = data_dict.get('cw_event_rule_description')
            sns_topic_name = data_dict.get('sns_topic_name')
            sns_display_name = data_dict.get('sns_display_name')
            sns_topic_sub_endpoint = data_dict.get('sns_topic_sub_endpoint')
            statefile_name = f"customization-statefiles/{AccountName}.tfstate"
            
            usernameslist = [formcontent[key] for key in formcontent.keys() if key.startswith('Username_')]
            usernames = list_conversion(usernameslist)
            # print(usernames)
          
            firstnames = [formcontent[key] for key in formcontent.keys() if key.startswith('FirstName_')]
            firstnames = list_conversion(firstnames)
            # print(firstnames)
            
            lastnames = [formcontent[key] for key in formcontent.keys() if key.startswith('LastName_')]
            lastnames = list_conversion(lastnames)
            
            tenant_emails = [formcontent[key] for key in formcontent.keys() if key.startswith('Tenant_email_')]
            tenant_emails = list_conversion(tenant_emails)
            
            
            subscriber_email_addresses = data_dict.get('subscriber_email_addresses')
            subscriber_email_addresses = subscriber_email_addresses.split(',')
            subscriber_email_addresses = list_conversion(subscriber_email_addresses)
            
            
            
            usercount = len(usernameslist)
            # print("length of list:",usercount)
        except Exception as e:
                    print("An exception occurred:", str(e))
                    
    for file in files_in_s3:
        
        try:        
            if file == "terraform.tfvars":
                
                # Initialize S3 and CodeCommit clients
                s3 = boto3.client('s3')
                codecommit = boto3.client('codecommit')
                
                # Specify the desired target file name and folder path
                target_folder_path = f'{AccountName}/terraform'  # Specify the target folder path within the repository
                target_file_name = file
                print(target_file_name)
            
                try:
                    # Download the Terraform configuration file from S3
                    response = s3.get_object(Bucket=bucket, Key=folder + file)
                    file_content = response['Body'].read().decode('utf-8')
    
                    # Modify the configuration data as needed using regular expressions
                    
                    replacements = {
                        r'user_name\s+=\s+".*?"': f'user_name = {usernames}',
                        r'user_given_name\s+=\s+".*?"': f'user_given_name = {firstnames}',
                        r'user_family_name\s+=\s+".*?"': f'user_family_name = {lastnames}',
                        r'user_emails\s+=\s+".*?"': f'user_emails = {tenant_emails}',  
                        r'counts\s+=\s+".*?"': f'counts = {usercount}',
                        # r'user_display_name\s+=\s+".*?"': f'user_display_name = {firstnames}',
                        r'group_display_name\s+=\s+".*?"': f'group_display_name = "{Group_Name}"',
                        r'target_id\s+=\s+".*?"': f'target_id = "{AccountID}"',
                        r'values\s+=\s+".*?"': f'values = ["{AccountID}"]',
                        r'description\s+=\s+".*?"': f'description = "{description}"',
                        r'budget_name\s+=\s+".*?"': f'budget_name = "{budget_name}"',
                        r'attribute_value\s+=\s+".*?"': f'attribute_value = "{SSOUserEmail}"',
                        # r'subscriber_email_addresses\s+=\s+\[.*?\]': f'subscriber_email_addresses = "{subscriber_email_addresses}"',
                        r'subscriber_email_addresses\s+=\s+".*?"': f'subscriber_email_addresses = {subscriber_email_addresses}',
                        
                        
                        r'cw_event_rule_name\s+=\s+".*?"': f'cw_event_rule_name = "{cw_event_rule_name}"',
                        r'cw_event_rule_description\s+=\s+".*?"': f'cw_event_rule_description = "{cw_event_rule_description}"',
                        r'cw_event_rule_accountid\s+=\s+".*?"': f'cw_event_rule_accountid = "{cw_event_rule_accountid}"',
                        r'sns_topic_name\s+=\s+".*?"': f'sns_topic_name = "{sns_topic_name}"',
                        r'sns_display_name\s+=\s+".*?"': f'sns_display_name = "{sns_display_name}"',
                        r'sns_topic_sub_endpoint\s+=\s+".*?"': f'sns_topic_sub_endpoint = "{sns_topic_sub_endpoint}"',
                        r'limit_amount\s+=\s+".*?"': f'limit_amount = {limit_amount}',
                        # r'statefile_name\s+=\s+".*?"': f'statefile_name = "{statefile_name}"'
                        
                        
                    }
            
                    for old_pattern, new_value in replacements.items():
                        file_content = re.sub(old_pattern, new_value, file_content)

                    #Specify the target file path including the folder path
                    target_file_path = f'{target_folder_path}/{target_file_name}'
            
                    # Fetch the latest commit ID for the branch
                    repository_name = repository_name  # Replace with your repository name
                    branch_name = branch_name  # Replace with your branch name
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
                except botocore.exceptions.ClientError as e:
                    print("Error:", e)
                    raise
                                
            elif file == "buildspec.yml":

                # Initialize S3 and CodeCommit clients
                s3 = boto3.client('s3')
                codecommit = boto3.client('codecommit')
                
                # Specify the desired target file name and folder path
                # target_folder_path = f'{AccountName}/terraform'  # Specify the target folder path within the repository
                target_file_name = file
                try:
                    # Download the Terraform configuration file from S3
                    response = s3.get_object(Bucket=bucket, Key=folder + file)
                    file_content = response['Body'].read().decode('utf-8')
                    
    
                    # Modify the configuration data as needed using regular expressions
                    
                    replacements = {
                        # r'user_name\s+=\s+".*?"': f'user_name = {usernames}',
                        r'cd \${CODEBUILD_SRC_DIR}/(.*?)/terraform': fr'cd ${{CODEBUILD_SRC_DIR}}/{AccountName}/terraform',
                    }
                    
                    for old_pattern, new_value in replacements.items():
                        file_content = re.sub(old_pattern, new_value, file_content)
                    
                    # print('new file created', file_content)
            
                    #Specify the target file path including the folder path
                    target_file_path = target_file_name
            
                    # Fetch the latest commit ID for the branch
                    repository_name = repository_name  # Replace with your repository name
                    branch_name = branch_name  # Replace with your branch name
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
                except botocore.exceptions.ClientError as e:
                    print("Error:", e)
                    raise
            
            elif file == "identitycenter.tf":
                # Initialize S3 and CodeCommit clients
                s3 = boto3.client('s3')
                codecommit = boto3.client('codecommit')
                
                # Specify the desired target file name and folder path
                target_folder_path = f'{AccountName}/terraform'  # Specify the target folder path within the repository
                target_file_name = file
                print(target_file_name)
                try:
                    # Download the Terraform configuration file from S3
                    response = s3.get_object(Bucket=bucket, Key=folder + file)
                    file_content = response['Body'].read().decode('utf-8')
                        
                    # Modify the configuration data as needed using regular expressions
                    replacements = {
                        # r'user_name\s+=\s+".*?"': f'user_name = {usernames}',
                        # r'cd \${CODEBUILD_SRC_DIR}/(.*?)/terraform': fr'cd ${{CODEBUILD_SRC_DIR}}/{AccountName}/terraform',
                        r'key\s+=\s+".*?"': f'key = "{statefile_name}"'
                        
                    }
                    
                    for old_pattern, new_value in replacements.items():
                        file_content = re.sub(old_pattern, new_value, file_content)

                    #Specify the target file path including the folder path
                    target_file_path = f'{target_folder_path}/{target_file_name}'
            
                    # Fetch the latest commit ID for the branch
                    repository_name = repository_name  # Replace with your repository name
                    branch_name = branch_name  # Replace with your branch name
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
                    
                except botocore.exceptions.ClientError as e:
                    print("Error:", e)
                    raise
                
            else:
            
                target_folder_path = f'{AccountName}/terraform'  # Specify the target folder path within the repository
                target_file_name = file
                
                print(target_file_name)
                try:
                    s3 = boto3.client('s3')
                    codecommit = boto3.client('codecommit')
                    # Download the Terraform configuration file from S3
                    response = s3.get_object(Bucket=bucket, Key=folder + file)
                    file_content = response['Body'].read().decode('utf-8')
                  
                    #Specify the target file path including the folder path
                    target_file_path = f'{target_folder_path}/{target_file_name}'
        
                    # Fetch the latest commit ID for the branch
                    repository_name = repository_name  # Replace with your repository name
                    branch_name = branch_name  # Replace with your branch name
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

                except Exception as e:
                    print("An exception occurred:", str(e))
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'SameFileContentException':
                print(f"Warning: SameFileContentException for file {file}. Skipping commit.")
            else:
                print(f"Error updating and committing file {file}: {e}")
            
def lambda_handler(event, context):
    formcontent = extractcsv(event)
    commitfiles(formcontent,event)
            
        
            
        
   