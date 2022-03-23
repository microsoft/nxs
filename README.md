# NXS: neural Network eXecution Service

NXS inference engine provides optimized inference runtime for both CPUs/GPUs using TVM compilation technique for both cloud and edge scenarios.

NXS allows users to register models and run inferences remotely via HTTP/REST frontends. It was desgined to allow developers to extend its capabilities easily such as scheduling algorithms, custom log collectors, etc...

## Features
- **TVM Optimized models.** NXS allows users to leverage TVM compiler to optimize models for a particular target device and deploy them on NXS for efficient inference.
- **Multiple frameworks.** NXS supports serveral well-known DL frameworks such as ONNX, TensorFlow to let users onboard vast amount of existings models. Furthermore, developers can easily extend the support of new frameworks due to NXS flexible and extendable design.
- **Batching** NXS allows requests to be batched to improve the througput of system if batching is supported.
- **Multiple sessions** NXS allows models to be shared and batched across multiple users/sessions. Each session might have different requirements such as SLA which NXS scheduler/dispatcher will have to consider independently. 
- **Pipeline execution** NXS was designed for many different usecases. 1) It can support single model execution such as classifier/detection models. 2) It can support backbone and heads design so users can execute a shared backend across many requests to extract features and route output features to coressponding head models to finalize the inferences.
- **Extendable design** NXS was designed to be extended to be used in many other usecases. Developers can easily extend NXS's interfaces to deploy new scheduling/dispatching policies, collect new types of logs or even support new DL frameworks.
- **Live model update** NXS helps developers to conveniently add or update model and its preprocessing/postprocessing code live without taking down the system for upgrade. This feature allows NXS to expand its capbabilities without interfering the current users.

## Get Started
### Build NXS-Edge container
```
docker build -f Dockerfile.edge -t nxs/edge .
```
### Start NXS-Edge container

The command below requires nvidia-docker. Check [this page](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) for installation instruction.

Make sure there is a GPU available to be used. Nvidia T4 is recommended.

```
export API_KEY="YOUR_API_KEY"
docker run -d --privileged --gpus=all -p 8080:80 -e API_KEY=$API_KEY nxs/edge
```

Note: To keep all your models persistant, map local paths to /app/tmp/db and /app/tmp/local
```
export API_KEY="YOUR_API_KEY"
export LOCAL_DB_PATH="$(pwd)/nxs_storage/db"
export LOCAL_STORAGE_PATH="$(pwd)/nxs_storage/local"
mkdir -p $LOCAL_DB_PATH
mkdir -p $LOCAL_STORAGE_PATH
docker run -d --privileged --gpus=all -p 8080:80 -e API_KEY=$API_KEY -v $LOCAL_DB_PATH:/app/tmp/db -v $LOCAL_STORAGE_PATH:/app/tmp/local nxs/edge
```

### Register and Run Yolox-s Object Detector

Register [Yolox-s](https://github.com/Megvii-BaseDetection/YOLOX/tree/main/demo/ONNXRuntime) model 
```
python examples/yolox_s/register.py --nxs_url http://localhost:8080 --nxs_api_key $API_KEY --model_url "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_s.onnx"
```
The program will return a generated "PIPELINE_UUID" to be used for doing inferences.

### Trigger inference on NXS

Change PIPELINE_UUID to the output of previous step.
```
python examples/yolox_s/run_infer.py --nxs_url "http://localhost:8080" --nxs_api_key $API_KEY --image_path "https://www.maxpixel.net/static/photo/1x/Dog-Cat-Friendship-Pets-Dachshund-Dog-Game-Cat-2059668.jpg" --pipeline_uuid PIPELINE_UUID
```

### Swagger page
```
http://localhost:8080/docs
```

## Code of Conduct

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/)
or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## License

This project is licensed under the [MIT License](LICENSE).
