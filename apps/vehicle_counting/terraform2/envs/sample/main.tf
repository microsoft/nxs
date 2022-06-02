# do not put special or uppercase characters in deployment_name
locals {
  deployment_name = "vcapptest"                                    # change this to your deployment name
}

module "nxs" {
  source = "../../modules/nxs-oss/root"  
  subscription_id       = ""                                  # user's subscription_id
  tenant_id             = ""                                  # user's tenant_id
  deployment_name       = local.deployment_name
  rg_name               = "nxs-${local.deployment_name}"
  location              = "westus2"                                  # location to deploy
  admin_group_object_id = ""                                  # admin group of this deployment
  ssl_cert_owner_email  = ""                                  # email to register for let's encrypt ssl certificate for secured connection between clients and nxs
  aks_cpu_node_vm_size  = "standard_d2s_v3"
  aks_min_cpu_node_count = 2  # minimum number of cpu nodes, should be at least 3 for Standard_D2s_v4  
  aks_max_cpu_node_count = 4  # maximum number of cpu nodes, should be at least aks_min_cpu_node_count
  aks_gpu_node_vm_size  = "Standard_NC4as_T4_v3"
  aks_min_gpu_node_count = 0  # minimum number of gpu nodes, should be at least 1
  aks_max_gpu_node_count = 2  # maximum number of gpu nodes, should be at least aks_min_gpu_node_count
  acr_login_server      = "nxsoss.azurecr.io"              # change this to acr where you store nxs container
  acr_username          = ""
  acr_password          = ""
  nxs_scheduler_image             = "nxsoss.azurecr.io/nxs/dev" # change nxsacrxxx.azurecr.io to your acr_login_server
  nxs_scheduler_image_tag         = "v0.0.1"
  nxs_workload_manager_image      = "nxsoss.azurecr.io/nxs/dev" # change nxsacrxxx.azurecr.io to your acr_login_server
  nxs_workload_manager_image_tag  = "v0.0.1"
  nxs_backend_monitor_image       = "nxsoss.azurecr.io/nxs/dev" # change nxsacrxxx.azurecr.io to your acr_login_server
  nxs_backend_monitor_image_tag   = "v0.0.1"
  nxs_backend_gpu_image           = "nxsoss.azurecr.io/nxs/dev" # change nxsacrxxx.azurecr.io to your acr_login_server
  nxs_backend_gpu_image_tag       = "v0.0.1"
  nxs_api_image                   = "nxsoss.azurecr.io/nxs/dev" # change nxsacrxxx.azurecr.io to your acr_login_server
  nxs_api_image_tag               = "v0.0.1"
  use_azure_redis_cache           = false
  az_redis_cache_capacity         = 2
  run_initializer                 = false
  nxs_initializer_image           = "nxsoss.azurecr.io/nxs/init"
  nxs_initializer_image_tag       = "v0.6.0"
  aks_max_num_api_containers      = 4
}

module "nxsapp" {
  source = "../../modules/app/root"  
  subscription_id       = ""                                  # user's subscription_id
  tenant_id             = ""                                  # user's tenant_id
  deployment_name       = local.deployment_name
  rg_name               = module.nxs.nxs_info.rg_info.name
  aks_base_info         = module.nxs.nxs_info.aks_info
  location              = "westus2"                                  # location to deploy (e.g., westus2)
  admin_group_object_id = ""                                  # admin group of this deployment
  ssl_cert_owner_email  = ""                                  # email to register for let's encrypt ssl certificate for secured connection between clients and nxs
  aks_cpu_node_vm_size  = "standard_d2s_v3"
  aks_min_cpu_node_count = 0  # minimum number of cpu nodes, should be at least 3 for Standard_D2s_v4  
  aks_max_cpu_node_count = 6  # maximum number of cpu nodes, should be at least aks_min_cpu_node_count  
  acr_login_server      = "nxsoss.azurecr.io"              # change this to acr where you store nxs container
  acr_username          = "nxsoss"
  acr_password          = ""
  api_domain_name_label = "vcapptest"              # e.g., nxsapp-vehicle-count ; the url to access app would be nxsapp-vehicle-count.<location>>.cloudapp.azure.com
  nxs_api_key           = module.nxs.nxs_info.nxs_api_key              # api key to access NXS cluster 
  nxsapp_api_container  = "ossnxs.azurecr.io/vcapi:v0.2.2"              # path to api container e.g., ossnxs.azurecr.io/vcapi:v0.1.2
  nxsapp_worker_container = "ossnxs.azurecr.io/vcworker:v0.2.2"            # path to worker container e.g., ossnxs.azurecr.io/vcworker:v0.1
  data_retention_days   = 18              # data retention in days for debug data
  delete_snapshot_retention_days = 3 # snapshot retention in days after deleting debug data
}