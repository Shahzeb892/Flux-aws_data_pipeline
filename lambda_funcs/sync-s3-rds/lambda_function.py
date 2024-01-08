import json
import boto3
import pandas as pd
import urllib.parse
import yaml
import io
import numpy as np

'''
Containerisation of Lambda functions is required as deployment packages of dependencies are too large.
resources: 
https://medium.com/@dogukannulu/cloud-engineering-project-trigger-amazon-lambda-with-s3-and-upload-data-to-rds-a8870175aa36
https://medium.com/@dogukannulu/how-to-create-amazon-lambda-function-with-the-container-image-dockerfile-6ab7927f5b99
'''


s3 = boto3.client('s3')
def lambda_handler(event, context):
    # All events must come only from fluxfielduploads/batch_upload_metadata/
    # this gets specified in the Trigger configuration
    # in this case an event is the upload of batch upload metadata (one yaml file)
    # Steps:
    # 1 get batch upload metadata yaml file
    # 3 from batch upload metadata yaml file extract names of image metadata yaml files uploaded to fluxfielduploads/metadata/, 
    # insert into AWS RDS postgrsql database
    # TODO: stage autolabelling...
    
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    #print(bucket,key)
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        print("CONTENT TYPE: " + response['ContentType'])
        #return response['ContentType']
    except Exception as e:
        print(bucket,key)
        print(e)
        print('Error getting object {} from bucket {}. Make sure they exist and your bucket is in the same region as this function.'.format(key, bucket))
        raise e
    
    #1 get the recently uploaded batch metadata yaml
    batch_upload_metadata = response.get("Body").read().decode("utf-8")
    #as python dictionary
    batch_upload_metadata_dict = yaml.safe_load(batch_upload_metadata)
    #loop through each file in batch_upload_metadata_dict["uploaded_metadata_file_names"]
    #
    key_prefix = batch_upload_metadata_dict["bucket_path_to_metadata"]
    bucket = batch_upload_metadata_dict["bucket_name"]
    for file in batch_upload_metadata_dict["uploaded_metadata_file_names"]:
        key = key_prefix+file
        try:
            response = s3.get_object(Bucket=bucket, Key=key)
            print("CONTENT TYPE: " + response['ContentType'])
        except Exception as e:
            print(e)
            print('Error getting object {} from bucket {}. Make sure they exist and your bucket is in the same region as this function.'.format(key, bucket))
            raise e
        this_image_metadata = response.get("Body").read().decode("utf-8")
        #as python dictionary
        this_image_metadata_dict = yaml.safe_load(this_image_metadata)
        
        #ensure keys are sorted alphabetically (column integrity)
        #print(this_image_metadata_dict.keys())
        columns = list(np.sort(list(this_image_metadata_dict.keys())))  
        row = []
        # exit()
        try:
            for field in columns:
                row.append(this_image_metadata_dict[field])
            metadata_df.loc[count] =row 
            count+=1
        except Exception as e:
            print(e)
            print("Error occured when syncing metadata entries with metadata dataframe...")
            raise e
    