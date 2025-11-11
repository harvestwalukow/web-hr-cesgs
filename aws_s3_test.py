import boto3
import os
from dotenv import load_dotenv

load_dotenv()

s3 = boto3.client('s3',
                aws_access_key_id=os.getenv('aws_access_key_id'),
                aws_secret_access_key=os.getenv('aws_secret_access_key'),
                region_name=os.getenv('region'))

try:
    response = s3.list_buckets()
    
    print('\nExisting buckets:')
    for bucket in response['Buckets']:
        print(f'  {bucket["Name"]}')
    
    # use bucket "iarr_dev"
    response = s3.list_objects_v2(Bucket='iarr-dev')
    print(response)
        
except Exception as e:
    print(f'Error: {e}')
