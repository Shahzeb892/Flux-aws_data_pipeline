# Script to build Nuclio
# This will run on the EC2 instance hosting the CVAT labelling tool
# Run this script from within it's parent directory (nuclio-build/)
# Requires that directory structure looks like:
'''
.
├── aws-data-pipeline
│   ├── cvat
│        ....
│   ├── build-cvat-nuclio-yolo
│   │   └── build.py
'''
import os

#This is not the latest version of Nuclio on purpose (it works for this implementation).
VERSION = "1.8.14" #This is not the latest version of Nuclio on purpose (it works for this implementation).
try:
    assert os.getcwd().split("/")[-1]=="build-cvat-nuclio-yolo"
except Exception as e:
    raise Exception("Nuclio Build FAILED: Run the build.py script from within it's parent directory: ie. cd PATH/TO/build-cvat-nuclio-yolo/ then try again.")

try:
    build_root = os.getcwd()
    cvat_path = "/".join(build_root.split("/")[:-1])+"/cvat"
    assert os.path.isdir(cvat_path)
except:
    raise Exception("Nuclio Build FAILED: Could not find ../cvat path from build.py.")

# print("Downloading nuctl-"+VERSION+"-linux-amd64")
#change dir here

## nuclio download and permissions

cd = "cd ../cvat"

pwd = "pwd"

wget = "wget https://github.com/nuclio/nuclio/releases/download/"+VERSION+"/nuctl-"+VERSION+"-linux-amd64"

chmod = "sudo chmod +x $(pwd)/nuctl-"+VERSION+"-linux-amd64"
# change here, was  $(pwd)/nuctl-, but it gets called from nuclio-build/, hence $(pwd)../cvat/nuctl-
softlink = "sudo ln -sf $(pwd)/nuctl-"+VERSION+"-linux-amd64 /usr/local/bin/nuctl"


### setting


commands = " && ".join([cd, pwd, wget, chmod, softlink])
#print(commands)

os.system(commands)

