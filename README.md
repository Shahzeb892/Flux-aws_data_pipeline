# aws-data-pipeline
Repo for aws infrastructure code, i.e. lambda functions to process uploads (fromn field-upload), rds-s3 database syncs... 


# lambda stuff here

# cvat stuff here


## Building CVAT-Nuclio-yolo (This only gets done once)

### Step 1 Clone cvat as a submodule referenced in the aws-data-pipeline repo
Run: 

cd aws-data-pipeline/ 

git submodule add https://github.com/opencv/cvat.git 

git submodule init

git submodule update

git submodule update --remote --merge


### Step 2
- Assuming cvat is cloned as a submodule build nuclio using the "build.py" script in aws-data-pipline/build-cvat-nuclio-yolo/. To do so run:

cd aws-data-pipeline/build-cvat-nuclio-yolo && python3 build.py


### Step 3 Clone Yolov5 as a Submodule 
- Need to clone yolo inside aws-data-pipeline/cvat/serverless/pytorch/ultralytics/yolov5/nuclio/
- Note: this path doesnt exist and needs to first be created.

Run:

cd aws-data-pipeline/cvat/serverless/pytorch/

mkdir ultralytics

mkdir ultralytics/yolov5

mkdir ultralytics/yolov5/nuclio

cd ultralytics/yolov5/nuclio

git submodule add https://github.com/ultralytics/yolov5.git

git submodule init

git submodule update

git submodule update --remote --merge

### Step 4 - Add auto-labelling yolov5 model weights.
- yolov5 weights with ".pt" pytorch suffix need to be copied to:

aws-data-pipeline/cvat/serverless/pytorch/ultralytics/yolov5/nuclio/

- note each time we want to use new model for autolabelling, the model needs to get added to the above directory, the path of the weights file also needs to get set in the nuclio function call which is in main.py and also lives in the directory (see below).

### Step 5 Configure docker-compose.serverless.yml, function.yaml and main.py files:
Templates of these files exist in build-cvat-nuclio-yolo/nuclio_scripts_templates

docker-compose.serverless.yml: 
- needs to have the same version (1.8.14) specified in the name of the image specified under the service:nuclio:image: field.
- Once configured, docker-compose.serverless.yml must exist in/as: aws-data-pipeline/cvat/components/serverless/docker-compose.serverless.yml 

main.py:
- specify the model name to be used (add names to the Models class and reference the model you desire)
- main.py must live in aws-data-pipeline/cvat/serverless/pytorch/ultralytics/yolov5/nuclio/

function.yaml:
- set the object detection labels you want in metadata:annotations:spec (These need to correspond to labels in CVAT)
- needs to live in the same dir as main.py, aws-data-pipeline/cvat/serverless/pytorch/ultralytics/yolov5/nuclio/

## Running all CVAT Docker Containers with serverless Nuclio integration of auto-labelling inference:

- To run/build the cvat docker images:
cd aws-data-pipline/cvat

docker compose -f docker-compose.yml -f components/serverless/docker-compose.serverless.yml up -d --build

- To Stop cvat conatiners:
cd aws-data-pipline/cvat

docker compose -f docker-compose.yml -f components/serverless/docker-compose.serverless.yml down

- To run the serverless nuclio integration of yolov5 inference in labelling (cvat docker containers must be running):
cd aws-data-pipline/cvat

./serverless/deploy_cpu.sh serverless/pytorch/ultralytics/yolov5



## Deploying CVAT Tool to an AWS EC2 host.