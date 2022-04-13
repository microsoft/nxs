# VEHICLE COUNTING APP

## Requirements
- Linux machine
- ACR
- Docker

## Build worker container and upload to your ACR
NOTE: Container MUST be built on Linux.

```
export ACR_LOGIN_SERVER_NAME=<YOUR ACR LOGIN SERVER NAME>
export ACR_LOGIN_SERVER=${ACR_LOGIN_SERVER_NAME}.azurecr.io
docker build -f apps/vehicle_counting/Dockerfile.api -t $ACR_LOGIN_SERVER/vcapi:v0.1 .
docker build -f apps/vehicle_counting/Dockerfile.worker -t $ACR_LOGIN_SERVER/vcworker:v0.1 .

az login
az acr login -n $ACR_LOGIN_SERVER_NAME
docker push $ACR_LOGIN_SERVER/vcapi:v0.1
docker push $ACR_LOGIN_SERVER/vcworker:v0.1
```

## Register detector and tracker to NXS
```
export NXS_URL="URL TO NXS CLUSTER"
export API_KEY="API KEY TO ACCESS NXS CLUSTER"
export TRACKER_MODEL_URL="URL TO TRACKER MODEL" # tracker is under release review process, please contact author to request for access
python apps/vehicle_counting/models/register_yolox-s.py
python apps/vehicle_counting/models/register_siammask_tracker.py --model_url $TRACKER_MODEL_URL
```

### Deploy to Azure
Edit apps/vehicle_counting/terraform/envs/sample/main.tf

```
# do not put special or uppercase characters in deployment_name
locals {
  deployment_name = "vc"                                    # change this to your deployment name
}

module "nxs" {
  source = "../../modules/root"  
  subscription_id       = ""                                  # user's subscription_id
  tenant_id             = ""                                  # user's tenant_id
  deployment_name       = local.deployment_name
  rg_name               = "nxsapp-${local.deployment_name}"
  location              = ""                                  # location to deploy (e.g., westus2)
  admin_group_object_id = ""                                  # admin group of this deployment
  ssl_cert_owner_email  = ""                                  # email to register for let's encrypt ssl certificate for secured connection between clients and nxs
  aks_cpu_node_vm_size  = "Standard_D2s_v4"
  aks_min_cpu_node_count = 2                                  # minimum number of cpu nodes
  aks_max_cpu_node_count = 6                                  # maximum number of cpu nodes, depends on how many videos you want to analyze concurrently
  acr_login_server      = ""                                  # change this to acr where you store nxs container
  acr_username          = ""
  acr_password          = ""
  api_domain_name_label = ""                                  # e.g., nxsapp-vehicle-count ; the url to access app would be nxsapp-vehicle-count.<location>>.cloudapp.azure.com
  nxs_url               = ""                                  # base url to access NXS cluster
  nxs_api_key           = ""                                  # api key to access NXS cluster 
  nxsapp_api_container  = ""                                  # path to api container in previous step e.g., $ACR_LOGIN_SERVER/vcapi:v0.1
  nxsapp_worker_container = ""                                # path to worker container in previous step e.g., $ACR_LOGIN_SERVER/vcworker:v0.1
}
```

Deploy
```
cd apps/vehicle_counting/terraform/envs/sample

terraform init

# check the deployment plan for anything unusual.
terraform plan

terraform apply
```

Once the deployment is finished, you can access the cluster using "AppUrl", "ApiKey" in the keyvault's secrets in the new resource group.

You can also access the swagger page stored in "AppSwaggerUrl" secret.