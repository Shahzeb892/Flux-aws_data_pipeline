import boto3
import pandas as pd
import urllib.parse
import yaml
import io
import os
import re
import numpy as np
from botocore.exceptions import ClientError
import logging
import pymysql
from sqlalchemy import create_engine, inspect, Table, Column, String, Integer, Float, Boolean, MetaData
'''
Containerisation of Lambda functions is required as deployment packages of dependencies are too large.
resources: 
https://medium.com/@dogukannulu/cloud-engineering-project-trigger-amazon-lambda-with-s3-and-upload-data-to-rds-a8870175aa36
https://medium.com/@dogukannulu/how-to-create-amazon-lambda-function-with-the-container-image-dockerfile-6ab7927f5b99
https://medium.com/@dogukannulu/establishing-a-vpc-for-amazon-s3-lambda-rds-and-ec2-8f3aa53b5429
'''

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

class GlobalVars:
    s3 = boto3.client('s3')
    #these are specified when defining the env vars when creating the Lambda Func
    db_name = os.getenv('database_name')
    db_username = os.getenv('database_username')
    db_password = os.getenv('database_password')
    db_endpoint = os.getenv('database_endpoint')
    db_port = 3306 # may need to change...
    database_uri = f"mysql+pymysql://{db_username}:{db_password}@{db_endpoint}:{db_port}/{db_name}"
    table_name = 'image_metadata'
    '''
    Both image metadata yamls and db are checked against the following column names
    TODO: handle user defined fields/columns (i.e. from field upload), 
    and when a new field is identified, update the database to include this new column (sql: "ALTER TABLE...")
    for now, if image metadata and db fields/columns dont match these below, then data is not populated in DB.
    Use columns_sorted below to maintain column order integrity.
    '''
    columns = [ "camera_number",
                "camera_name",
                "class_mappings",
                "crop",
                "customer",
                "farm_location",
                "image_file_name",
                "image_capture_datetime_utc_iso",
                "image_file_path_S3",
                "image_metadata_file_path_S3",
                "lens_name",
                "robot_model",
                "yolo_text_file_data",
                "auto_labelled_yolo_text_file_data",
                "filtered_auto_labelled_yolo_text_file_data",
                "auto_labelled", 
                "auto_labels_filtered",
                "manually_labelled",
                "upload_start_datetime_utc_iso",
                "batch_upload_metadata_filename",
                "auto_labels_filtered_by_user",
                "manually_labelled_by_user"]
    columns_sorted = list(np.sort(columns))
    
    #how we identify each table entry
    primary_key = "image_file_name"
    # this maps each field/col to a sql table datatype
    # note, as of time of writing this, all fields are of type string except "auto_labelled", "auto_labels_filtered", "manually_labelled", which are bool
    columns_dtypes = {}
    for col in columns_sorted:
        if col in ["auto_labelled", "auto_labels_filtered", "manually_labelled"]:
            columns_dtypes[col] = Boolean
        else:
            columns_dtypes[col] = String
        #TODO: add new dtypes for new fields as required.


    

def get_batch_upload_metadata_dict(bucket,key):
    try:
        response = GlobalVars.s3.get_object(Bucket=bucket, Key=key)
        # print("CONTENT TYPE: " + response['ContentType'])
        #return response['ContentType']
    except Exception as e:
        print('Failed to get object {} from bucket {} due to exception: {}'.format(key, bucket, e))
        log.info('Failed to get object {} from bucket {} due to exception: {}'.format(key, bucket, e))
        raise e
    log.info('Succesfully retrieved batch upload metadata yaml {} from s3 bucket {}'.format(key, bucket))
    #1 get the recently uploaded batch metadata yaml
    batch_upload_metadata = response.get("Body").read().decode("utf-8")
    #as python dictionary
    batch_upload_metadata_dict = yaml.safe_load(batch_upload_metadata)

    return batch_upload_metadata_dict

def get_populated_df(batch_upload_metadata_dict):
    
    #create empty df with columns from image metadata fields
    df = pd.DataFrame(columns=GlobalVars.columns_sorted)

    key_prefix = batch_upload_metadata_dict["bucket_path_to_metadata"]
    bucket = batch_upload_metadata_dict["bucket_name"]

    #loop through each file in batch_upload_metadata_dict["uploaded_metadata_file_names"]
    # add it to the df (checking that fields from the image metadata yaml match what is expected as per GlobalVars.columns_sorted)
    count = 0
    for file in batch_upload_metadata_dict["uploaded_metadata_file_names"]:
        key = key_prefix+file
        try:
            response = GlobalVars.s3.get_object(Bucket=bucket, Key=key)
        except Exception as e:
            print('Failed to get object {} from bucket {} due to exception: {}'.format(key, bucket, e))
            log.info('Failed to get object {} from bucket {} due to exception: {}'.format(key, bucket, e))
            raise e
        this_image_metadata = response.get("Body").read().decode("utf-8")
        log.info("Succesfully")
        #as python dictionary
        this_image_metadata_dict = yaml.safe_load(this_image_metadata)
        
        #ensure keys from image metadata are sorted alphabetically (column integrity)
        columns = list(np.sort(list(this_image_metadata_dict.keys())))

        # check that incoming fields match what the DB is expecting.
        # TODO: make this more dynamic by allowing new fields/missing fields.
        try:
            assert(columns == GlobalVars.columns_sorted)  
        except Exception as e:
            new_fields = []
            missing_fields = []
            for field in columns:
                if field not in GlobalVars.columns_sorted:
                    new_fields.append(field)
            for field in GlobalVars.columns_sorted:
                if field not in columns:
                    missing_fields.append(field)
            log.info("Fields from image metadata file {} do not match the column fields of the DB. \nUnexpected fields provided in the image metadata are: {}. \nExpected fields that are missing from the image metadata are: {}".format(file,new_fields,missing_fields))
            raise e
        row = []
        for field in columns:
            row.append(this_image_metadata_dict[field])
        df.loc[count] =row 
        count+=1
    return df

def connect_to_rds_and_upload_df():
    '''
    Connects to the RDS DB using create_engine
    Lists available RDS tables using inspect().get_table_names()
    If GlobalVars.table_name ("image_metadata") is not in this list, then we create a table called 'image_metadata' and populate it with the df
    '''
    log.info('Attempting to connect to RDS...')
    try:
        engine = create_engine(GlobalVars.database_uri)
        log.info("Succesfully connected to RDS Database.")
    except Exception as e:
        log.info("Failed to connect to the RDS instance due to the following exception {}.".format(e))
        raise e
    
    log.info("Checking if Table with name {} exists.".format(GlobalVars.table_name))
    try:
        insp = inspect(engine)
        tables = insp.get_table_names()
        if GlobalVars.table_name not in tables:
            log.info("Table '{}' not found. Creating new table in RDS called '{}'.".format(GlobalVars.table_name, GlobalVars.table_name))
            #required to create a table. Dont confuse with image metadata.
            db_metadata_obj = MetaData()

            # Dynamically add columns to table: (table name and db_metadata_obj must be first two args)
            args = [GlobalVars.table_name, 
                    db_metadata_obj]
            for col in GlobalVars.columns_sorted:
                if col == GlobalVars.primary_key:
                    args.append(Column(col, GlobalVars.columns_dtypes[col], primary_key=True))
                else:
                    args.append(Column(col, GlobalVars.columns_dtypes[col]))

            sql_table = Table(*args)
            db_metadata_obj.create_all(engine)
            log.info("Successfully created new table {} in RDS".format(GlobalVars.table_name))
    except:
        #TODO: Continue here.
        pass







def lambda_handler(event, context):
    # All events must come only from fluxfielduploads/batch_upload_metadata/
    # this gets specified in the Trigger configuration
    # in this case an event is the upload of batch upload metadata (one yaml file)
    # Steps:
    # 1 get batch upload metadata yaml file
    # 3 from batch upload metadata yaml file extract names of image metadata yaml files uploaded to fluxfielduploads/metadata/, 
    # insert into df that gets uploaded to the AWS RDS MySQL database
    # TODO: stage autolabelling...
    
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    
    #1 get the recently uploaded batch metadata yaml as a python dictionary
    batch_upload_metadata_dict = get_batch_upload_metadata_dict(bucket,key)

    # create and populate a df with incoming image metadata yamls
    df =  get_populated_df(batch_upload_metadata_dict)

    #connect to the DB and add data to the table ("image_metadata"). If it doesnt exist, it gets created and populated.

    #loop through each file in batch_upload_metadata_dict["uploaded_metadata_file_names"]
    #
    key_prefix = batch_upload_metadata_dict["bucket_path_to_metadata"]
    bucket = batch_upload_metadata_dict["bucket_name"]
    for file in batch_upload_metadata_dict["uploaded_metadata_file_names"]:
        key = key_prefix+file
        try:
            response = GlobalVars.s3.get_object(Bucket=bucket, Key=key)
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
            df.loc[count] =row 
            count+=1
        except Exception as e:
            print(e)
            print("Error occured when syncing metadata entries with metadata dataframe...")
            raise e
    