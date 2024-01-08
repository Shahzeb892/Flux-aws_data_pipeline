import json
import boto3
import pandas as pd
import urllib.parse
import yaml
import io
import numpy as np

s3 = boto3.client('s3')
def lambda_handler(event, context):
    # All events must come only from fluxfielduploads/batch_upload_metadata/
    # this gets specified in the Trigger configuration
    # in this case an event is the upload of batch upload metadata (one yaml file)
    # Steps:
    # 1 get batch upload metadata yaml file
    # 2 get metadata_dataframe.csv stored in fluxfielduploads/metadata_dataframe/
    # 3 from batch upload metadata yaml file extract names of image metadata 
    # yaml files uploaded to fluxfielduploads/metadata/, 
    # insert into metadataframe, dump mddf to s3. OVERWRITES!
    
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
    
    #1
    batch_upload_metadata = response.get("Body").read().decode("utf-8")
    #as python dictionary
    batch_upload_metadata_dict = yaml.safe_load(batch_upload_metadata)
    #print(batch_upload_metadata_dict)
    #2 get metadata_dataframe.csv TODO: This will eventually need to change to a database setup.
    mddf_key = "metadata_dataframe/metadataframe.csv"
    
    try:
        response = s3.get_object(Bucket=bucket, Key=mddf_key)
        print("CONTENT TYPE: " + response['ContentType'])
    except Exception as e:
        print(e)
        print('Error getting object {} from bucket {}. Make sure they exist and your bucket is in the same region as this function.'.format(key, bucket))
        raise e
    csv_content = response.get("Body").read().decode("utf-8")
    metadata_df = pd.read_csv(io.StringIO(csv_content))
    
    # count is number of entries in the dataframe, and the next index for a new entry.
    count = len(metadata_df)
    
    #3 
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
    
    # text buffer
    stringio = io.StringIO()

    metadata_df.to_csv(stringio, index=False)
    bytesio = io.BytesIO(stringio.getvalue().encode())
    # saving a data frame to a buffer (same as with a regular file):
    # df.to_csv(bytesio, index=False)
    try:
        s3.upload_fileobj(bytesio, bucket, mddf_key)
    except Exception as e:
        print(e)
        print("Data frame upload failed!")
        raise e
    #     return {
    #     'statusCode': 255,
    #     'body': json.dumps('Dataframe sync FAILED.')
    # }
        
    return {
        'statusCode': 200,
        'body': json.dumps('Dataframe Syncd.')
    }