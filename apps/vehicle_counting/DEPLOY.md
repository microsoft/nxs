# VEHICLE COUNTING APP

## Requirements
- Linux machine
- ACR
- Docker

## NOTE:
```
This version will deploy NXS cluster along with Vehicle Counting App cluster. 
It does not require existing NXS cluster.
```

## Build worker container and upload to your ACR
NOTE: Container MUST be built on Linux.

```
export ACR_LOGIN_SERVER_NAME=<YOUR ACR LOGIN SERVER NAME>
export ACR_LOGIN_SERVER=${ACR_LOGIN_SERVER_NAME}.azurecr.io
# Build nxs containers
docker build -f Dockerfile -t ${ACR_LOGIN_SERVER}.azurecr.io/nxs/dev:v0.1.0 .

# Build app containers
docker build -f apps/vehicle_counting/Dockerfile.api -t $ACR_LOGIN_SERVER/vcapi:v0.1 .
docker build -f apps/vehicle_counting/Dockerfile.worker -t $ACR_LOGIN_SERVER/vcworker:v0.1 .

az login
az acr login -n $ACR_LOGIN_SERVER_NAME
docker push ${ACR_LOGIN_SERVER}.azurecr.io/nxs/dev:v0.1.0
docker push $ACR_LOGIN_SERVER/vcapi:v0.1
docker push $ACR_LOGIN_SERVER/vcworker:v0.1
```

## Deploy to Azure
Edit apps/vehicle_counting/terraform/envs/sample/main.tf

```
# do not put special or uppercase characters in deployment_name
locals {
    # shared configurations
    base = {
        deployment_name         = "vcapptest"                           # this will be resource group name
        subscription_id         = ""                                    # user's subscription_id
        tenant_id               = ""                                    # user's tenant_id
        location                = ""                                    # location to deploy (e.g., westus2)
        admin_group_object_id   = ""                                    # admin group of this deployment
        ssl_cert_owner_email    = ""                                    # email to register for let's encrypt ssl certificate
    }
    
    # nxs configurations
    nxs_config = {
        # aks configs
        aks = {
            aks_cpu_node_vm_size = "standard_d2s_v3"
            aks_min_cpu_node_count = 3
            aks_max_cpu_node_count = 10
            aks_gpu_node_vm_size  = "Standard_NC4as_T4_v3"
            aks_min_gpu_node_count = 0
            aks_max_gpu_node_count = 10
        }

        # container register configs - change this to acr where you store nxs container
        acr = {
            acr_login_server      = ""
            acr_username          = ""
            acr_password          = ""
        }

        # container configs
        containers = {
            scheduler = {
                nxs_scheduler_image             = "nxsoss.azurecr.io/nxs/dev" #replace with nxs container
                nxs_scheduler_image_tag         = "v0.1.0"                    #replace with nxs container version
            }
            workload_manager = {
                nxs_workload_manager_image      = "nxsoss.azurecr.io/nxs/dev" #replace with nxs container
                nxs_workload_manager_image_tag  = "v0.1.0"                    #replace with nxs container version
            }
            backend_monitor = {
                nxs_backend_monitor_image       = "nxsoss.azurecr.io/nxs/dev" #replace with nxs container
                nxs_backend_monitor_image_tag   = "v0.1.0"                    #replace with nxs container version
            }
            backend_gpu = {
                nxs_backend_gpu_image           = "nxsoss.azurecr.io/nxs/dev" #replace with nxs container
                nxs_backend_gpu_image_tag       = "v0.1.0"                    #replace with nxs container version
            }
            frontend = {
                nxs_api_image                   = "nxsoss.azurecr.io/nxs/dev" #replace with nxs container
                nxs_api_image_tag               = "v0.1.0"                    #replace with nxs container version
                min_num_frontend_replicas       = 2
                max_num_frontend_replicas       = 8
                enable_api_v1                   = false
            }
            model_initializer = {
                nxs_initializer_image           = "nxsoss.azurecr.io/nxs/init"
                nxs_initializer_image_tag       = "v0.1.0"
                run_initializer                 = false                           # should be false
            }
        }

        # redis configs
        redis = {
            use_azure_redis_cache = true

            azure_redis_cache = {
                # applicable when use_azure_redis_cache is true
                azure_redis_cache_sku               = "Standard"
                azure_redis_cache_family_type       = "C"
                azure_redis_cache_capacity          = 2
            }
        }

        # [OPTIONAL CONFIGS]
        # db configs
        db = {
            db_autoscale_max_throughput             = 4000
        }
    }

    # nxsapp configurations
    nxsapp_config = {
        # add new cpupool to run nxsapp
        aks = {
            aks_app_cpu_pool_vm_size = "standard_d2s_v3"
            aks_app_cpu_pool_min_node_count = 0
            aks_app_cpu_pool_max_node_count = 10
        }

        # container register configs - change this to acr where you store nxs container
        acr = {
            acr_login_server      = ""
            acr_username          = ""
            acr_password          = ""
        }

        # container configs
        containers = {
            app_frontend = {
                nxsapp_api_image                = "ossnxs.azurecr.io/vcapi"       #replace with app api container
                nxsapp_api_tag                  = "v0.1"                          #replace with app api container version
            }
            app_worker = {
                nxsapp_worker_image             = "ossnxs.azurecr.io/vcworker"    #replace with app worker container
                nxsapp_worker_tag               = "v0.1"                          #replace with app worker container version
            }
        }

        # [OPTIONAL CONFIGS]
        # app configs
        app = {
            app_report_counts_interval  = 900
            detector_uuid               = "bbff897256c9431eb19a2ad311749b39"
            tracker_uuid                = "451ffc2ee1594fe2a6ace17fca5117ab"
        }

        # db configs
        db = {
            db_autoscale_max_throughput             = 4000
            db_item_ttl                             = -1    # Set to positive number to automatically delete items after TTL
        }

        # storage configs
        storage = {
            data_retention_days                     = 18    # data retention in days for debug data
            delete_snapshot_retention_days          = 3     # snapshot retention in days after deleting debug data
        }
    }
}

module "nxs" {
    source = "git::https://github.com/microsoft/nxs.git//terraform/modules/nxs-oss/root?ref=v0.3.1"
    base = local.base
    nxs_config = local.nxs_config
}

module "nxsapp" {
    source                      = "../../modules/app/root"
    base                        = local.base
    aks_base_info               = module.nxs.nxs_info.aks_info
    aks_configs_base_info       = module.nxs.nxs_info.aks_configs_info
    aks_deployments_base_info   = module.nxs.nxs_info.aks_deployments_info
    nxs_api_key                 = module.nxs.nxs_info.nxs_api_key
    app_config                  = local.nxsapp_config
}

output nxs_url {
  value = module.nxs.nxs_url
}

output nxsapp_url {
  value = module.nxsapp.nxsapp_url
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

## Register detector and tracker to NXS
```
export NXS_URL="URL TO NXS CLUSTER"
export API_KEY="API KEY TO ACCESS NXS CLUSTER"
export TRACKER_MODEL_URL="URL TO TRACKER MODEL" # tracker is under release review process, please contact author to request for access
python apps/vehicle_counting/models/register_yolox-s.py
python apps/vehicle_counting/models/register_siammask_tracker.py --model_url $TRACKER_MODEL_URL
```