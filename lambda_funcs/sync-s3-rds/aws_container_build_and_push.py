import os
commands = [
    "cd ~/AWS-DATA-PIPELINE/aws-data-pipeline/lambda_funcs/sync-s3-rds/",
    "aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin 696272199193.dkr.ecr.ap-southeast-2.amazonaws.com",
    "docker build -t lambda-function-docker-repository .",
    "docker tag lambda-function-docker-repository:latest 696272199193.dkr.ecr.ap-southeast-2.amazonaws.com/lambda-function-docker-repository:latest",
    "docker push 696272199193.dkr.ecr.ap-southeast-2.amazonaws.com/lambda-function-docker-repository:latest"

]
command = " && ".join(commands)
os.system(command)
