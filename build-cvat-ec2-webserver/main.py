import json
import base64
from PIL import Image
import io
import torch


class Models:
    
    # each .pt model file needs to live in aws-data-pipeline/cvat/serverless/pytorch/ultralytics/yolov5/nuclio/
    YOLOV5N_MODEL_1 = 'pyes_onion_640_yolov5n.pt'

def init_context(context):
    context.logger.info("Init context...  0%")

    # Read the DL model
    #model = torch.hub.load('/opt/nuclio/ultralytics/yolov5', "custom", path='/opt/nuclio/your-custom_model.pt', source="local")
    model = torch.hub.load('/opt/nuclio/yolov5', "custom", path='/opt/nuclio/'+Models.YOLOV5N_MODEL_1, source="local")
    context.user_data.model = model

    context.logger.info("Init context...100%")

def handler(context, event):
    context.logger.info("Run yolo-v5 model")
    data = event.body
    buf = io.BytesIO(base64.b64decode(data["image"]))
    threshold = float(data.get("threshold", 0.3))
    context.user_data.model.conf = threshold
    image = Image.open(buf)
    yolo_results_json = context.user_data.model(image).pandas().xyxy[0].to_dict(orient='records')

    encoded_results = []
    for result in yolo_results_json:
        encoded_results.append({
            'confidence': result['confidence'],
            'label': result['name'],
            'points': [
                result['xmin'],
                result['ymin'],
                result['xmax'],
                result['ymax']
            ],
            'type': 'rectangle'
        })

    return context.Response(body=json.dumps(encoded_results), headers={},
        content_type='application/json', status_code=200)