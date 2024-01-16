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
import time
import pymysql
from aws_lambda_powertools import Logger
from sqlalchemy import create_engine, inspect, text, Table, Column, String, Integer, Float, Boolean, MetaData
log = Logger()
'''
Containerisation of Lambda functions is required as deployment packages of dependencies are too large.
resources: 
https://medium.com/@dogukannulu/cloud-engineering-project-trigger-amazon-lambda-with-s3-and-upload-data-to-rds-a8870175aa36
https://medium.com/@dogukannulu/how-to-create-amazon-lambda-function-with-the-container-image-dockerfile-6ab7927f5b99
https://medium.com/@dogukannulu/establishing-a-vpc-for-amazon-s3-lambda-rds-and-ec2-8f3aa53b5429
'''

#logging.basicConfig(level=logging.INFO,
                    # format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#logging.getLogger()#(__name__)

class GlobalVars:
    s3 = boto3.client('s3')
    #these are specified when defining the env vars when creating the Lambda Func
    db_name = os.getenv('database_name')
    db_username = os.getenv('database_username')
    db_password = os.getenv('database_password')
    db_endpoint = os.getenv('database_endpoint')
    db_port = 3306 # aws defined for rds
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
                "camera_model",
                "class_mappings",
                "crop",
                "customer",
                "farm_location",
                "image_file_name",
                "image_capture_datetime_utc_iso",
                "image_file_path_S3",
                "image_metadata_file_path_S3",
                "lens_model",
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
                "manually_labelled_by_user",
                "gps_coordinates",
                "velocity_mmps",
                "focal_point_height_above_crop_bed_mm"]
    columns_sorted = list(np.sort(columns))
    
    #how we identify each table entry
    primary_key = "image_file_name"
    # this maps each field/col to a sql table datatype
    # note, as of time of writing this, all fields are of type string except "auto_labelled", "auto_labels_filtered", "manually_labelled", which are bool
    columns_dtypes = {}
    for col in columns_sorted:
        if col in ["auto_labelled", "auto_labels_filtered", "manually_labelled"]:
            columns_dtypes[col] = Boolean
        elif col in ["velocity_mmps", "focal_point_height_above_crop_bed_mm"]:
            columns_dtypes[col] = Float
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
        log.error('Failed to get object {} from bucket {} due to exception: {}'.format(key, bucket, e))
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
            log.error('Failed to get object {} from bucket {} due to exception: {}'.format(key, bucket, e))
            raise e
        this_image_metadata = response.get("Body").read().decode("utf-8")
        log.info("Succesfully loaded image metadata file {} from bucket {} batch_upload_metadata file from S3.".format(key, bucket))
        #as python dictionary
        this_image_metadata_dict = yaml.safe_load(this_image_metadata)
        
        #ensure keys from image metadata are sorted alphabetically (column integrity)
        columns = list(np.sort(list(this_image_metadata_dict.keys())))

        # check that incoming fields match what the DB is expecting.
        # TODO: make this more dynamic by allowing new fields/missing fields.
        # TODO: Whats the error handling policy? write off the whole batch sync if one fails? Or ignore fails and upload what can be uploaded? (Latter)
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
            log.error("Fields from image metadata file {} do not match the column fields of the DB. \nUnexpected fields provided in the image metadata are: {}. \nExpected fields that are missing from the image metadata are: {}".format(file,new_fields,missing_fields))
            raise e
        row = []
        for field in columns:
            row.append(this_image_metadata_dict[field])
        df.loc[count] =row 
        count+=1
    return df

def connect_to_rds():
    log.info('Attempting to connect to RDS...')
    try:
        engine = create_engine(GlobalVars.database_uri)
        print("Succesfully connected to RDS Database.")
        log.info("Succesfully connected to RDS Database.")
    except Exception as e:
        log.error("Failed to connect to the RDS instance due to the following exception {}.".format(e))
        raise e
    return engine

#not needed, df.to_sql, can create it for us.
def create_new_table(engine):
    try:
        log.info("Creating new table in RDS called '{}'.".format(GlobalVars.table_name))
        #required to create a table. 
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
        log.info("Created new table {} in RDS".format(GlobalVars.table_name))

        ''' 
            Not sure if creating the table is async/takes time to show up.
            So putting this while loop here to check the table exists before proceeding to upload data.
        ''' 
        log.info("Confirming table {} exists...".format(GlobalVars.table_name))
        attempt_num = 0
        max_attempts = 300
        sleep_val = .2
        max_time_secs = max_attempts/(1.0/sleep_val)
        while True:
            if attempt_num == max_attempts:
                log.error("Table {} was created but is still not visible after {} seconds".format(GlobalVars.table_name, max_time_secs))
                raise Exception("Table {} was created but is still not visible after {} seconds. Try increasing the value for 'max_attempts' (see lambda func), which is currently set to {}".format(GlobalVars.table_name, max_time_secs,max_attempts))
            time.sleep(sleep_val)
            insp = inspect(engine)
            tables = insp.get_table_names()
            if GlobalVars.table_name in tables:
                log.info('Table creation confirmed for {}. Proceeding to upload...')
                break
            attempt_num+=1
        return engine
    except Exception as e:
        log.error("Failed to create new table with name {} due to exception {}.".format(GlobalVars.table_name, e))
        log.error("Upload to RDS Failed!")
        raise e

def table_exists(engine) -> bool:
    '''
    Connects to the RDS DB using create_engine
    Lists available RDS tables using inspect().get_table_names()
    If GlobalVars.table_name ("image_metadata") is not in this list, then we create a table called 'image_metadata' and populate it with the df
    '''
    
    log.info("Checking if Table with name {} exists.".format(GlobalVars.table_name))
    try:
        #insp = inspect(engine)
        #tables = engine.table_names() #insp.get_table_names()
        if engine.dialect.has_table(engine, GlobalVars.table_name) == False:# GlobalVars.table_name not in tables:
            log.info("Table '{}' not found.".format(GlobalVars.table_name))
            return False
            
        else:
            log.info("Table {} exists. Proceeding to upload latest image metadata to table {} in RDS...".format(GlobalVars.table_name, GlobalVars.table_name))
            return True

    except Exception as e:
        log.error("Failed to determine if table {} exists or not due to the exception {}...".format(GlobalVars.table_name, e))
        raise e


def upload_df_to_RDS_table(df, engine):
    log.info("Uploading data to RDS...")
    try:
        # in this lambda func, we can assume incoming data is unique and doesnt exist in the table
        df.to_sql(GlobalVars.table_name, con=engine, if_exists='append', index=False)
        
        #check new entries (only primary_key column) are in the Table - overkill?
        sql_query = "SELECT {} FROM {}".format(GlobalVars.primary_key, GlobalVars.table_name)
        
        db_df_primary_key_col = pd.read_sql(sql_query, engine)
        recent_uploads_np = np.array(df[GlobalVars.primary_key])

        db_df_primary_key_col_as_np = np.array(db_df_primary_key_col[GlobalVars.primary_key])
        for i in range(len(recent_uploads_np)):
            assert recent_uploads_np[i] in db_df_primary_key_col_as_np
        log.info("Data uploaded to RDS succesfully.")
    except Exception as e:
        log.error("Failed to upload data to RDS due to {}".format(e))
        raise e

def check_existing_table_columns(engine, table_name):
    # this is a work around after struggling to get other approaches to work
    sql_query = "SELECT * FROM {}".format(table_name)
    result = pd.read_sql(sql_query, engine)
    if len(result.keys()):
        #table exists and has columns 
        # need to check cols
        cols = list(result.keys())
        try:
            assert(cols==GlobalVars.columns_sorted)
            log.info("Table column names match the expected column names.")
        except AssertionError as e:
            log.error("Error: {}. Table column names do not match expected column names. Upload to RDS failed.".format(e))
            #TODO: handle case where table has different columns... create new table? OR, Modify the existing table to include old and new cols?
            raise Exception("Error: {}. Table column names do not match expected column names. Upload to RDS failed.".format(e))
    else:
        log.info("No table with table_name {} exists. It will be created now.".format(GlobalVars.table_name))
    result.close()
    return
    
    

def lambda_handler(event, context):
    # All events must come only from fluxfielduploads/batch_upload_metadata/
    # this gets specified in the Trigger configuration
    # in this case an event is the upload of batch upload metadata (one yaml file)
    
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    
    #1 get the recently uploaded batch metadata yaml as a python dictionary
    batch_upload_metadata_dict = get_batch_upload_metadata_dict(bucket,key)

    # create and populate a df with incoming image metadata yamls
    df =  get_populated_df(batch_upload_metadata_dict)

    # convert ''s to NaNs (Null in SQL)
    df = df.replace('', np.nan)
    # convert Nones to NaNs
    df = df.fillna(value=np.nan)
    engine = connect_to_rds()
    
   
    # check first if table exists, 
    # if so assert that columns are as expected
    
    if GlobalVars.table_name in inspect(engine).get_table_names():
        # connection = engine.connect()
        with engine.connect() as conn:
            res = conn.execute(text("SELECT * FROM {};".format(GlobalVars.table_name)))
            table_cols = list(res.keys())
            # res.close()
        # connection.close()
        #check table columns match the image metadata fields as specified in GlobalVars.columns_sorted.
        try:
            assert(table_cols==GlobalVars.columns_sorted)
            log.info("Table column names match the expected column names.")
        except AssertionError as e:
            log.error("Error: {}. Table column names do not match expected column names. Upload to RDS failed.".format(e))
            #TODO: handle case where table has different columns...
            raise Exception("Error: {}. Table column names do not match expected column names. Upload to RDS failed.".format(e))
        
    else:
        #table doesnt exist, create it in create_new_table. this also sets dtypes (as opposed to df.to_sql).
        engine = create_new_table(engine)
        log.info("Table with table_name {} doesn't exist. A new table with that table name will be created and populated with the latest batch upload.")
    upload_df_to_RDS_table(df, engine)
    log.info("Batch Upload of S3 image metadata is succesfully sync'd with RDS database.")