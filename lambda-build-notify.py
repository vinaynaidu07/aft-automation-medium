import json
import boto3


def lambda_handler(event, context):
    event = json.dumps(event)
    
    print('***********')
    print(event)
    
    sns = boto3.client('sns')
    
    # Assuming 'event' is your JSON data
    event_data = json.loads(event)
    
    # Accessing the first record
    first_record = event_data['Records'][0]
    
    # Accessing 'Sns' within the first record
    sns_data = first_record['Sns']
    
    # Accessing 'Message' within the Sns data
    message_data_str = sns_data['Message']
    
    # Parsing the 'Message' string to a dictionary
    message_data = json.loads(message_data_str)
    
    # Accessing 'build-status' within the parsed 'Message' data
    build_status = message_data.get('detail', {}).get('build-status')
    
    print(build_status)
    
    status = "The build status of the account customization is :",build_status
    
    
    sns.publish(
        TopicArn='sns-topic-arn',
        Message=json.dumps(status)
    )

    return {
        'statusCode': 200,
        'body': 'Event customization and publishing to SNS successful'
    }