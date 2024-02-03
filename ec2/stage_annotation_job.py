import click

'''
This script is to be used by the CVAT administrator who stages jobs for annotation with cvat. 


Core Functionality:
- given crop (SELECT * WHERE crop='onion')
- is currently not being labelled (WHERE manually_labelled_by_user Is NULL)
- max_number of images.
Either does a direct cp from fluxfielduploads to fluxannotation, or dumps a yaml (somewhere in s3) that triggers the cp via lambda.

Next thing to consider is triggering a new job/task based on the query, for a given user. 
--- Either via cli on host (not the same host as rds-connect), or via UI.
'''


def update_db():
    #needed for inserting the labeller name 
    pass


@click.command()
@click.option('--table_name', help= 'Name of the database table to query')
@click.option('--crop',help= "Required, lowercase name of the crop. Select images from this crop.")
@click.option('--max_num', help= "Required. The max number of images to stage for labelling")
@click.option('--customer', help= "Optional, customer names are in ALL capital letters.") 
@click.option('--labeller_username', help= "This is the (first) name of the labeller who will be responsible for labelling these images. If multiple users, separate with commas (no trailing comma).")
#todo:
#@click.option('--min_timestamp_utc', help = "Select images with UTC capture timestamp after this UTC time stamp.")
#@click.option('--max_timestamp_utc', help = "Select images with UTC capture timestamp before this UTC time stamp.")
def 



if __name__ == "__main__":
