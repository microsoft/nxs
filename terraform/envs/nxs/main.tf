# do not put special or uppercase characters in deployment_name
locals {
  deployment_name = "oss"                                    # change this to your deployment name
}

module "nxs" {
  source = "../../modules/nxs-oss/root"  
  subscription_id       = ""                                  # user's subscription_id
  tenant_id             = ""                                  # user's tenant_id
  deployment_name       = local.deployment_name
  rg_name               = "nxs-${local.deployment_name}"
  location              = ""                                  # location to deploy (e.g., westus2)
  admin_group_object_id = ""                                  # admin group of this deployment
  ssl_cert_owner_email  = ""                                  # email to register for let's encrypt ssl certificate for secured connection between clients and nxs
  aks_cpu_node_vm_size  = "Standard_D2s_v4"
  aks_min_cpu_node_count = 3  # minimum number of cpu nodes, should be at least 3 for Standard_D2s_v4 with oss-redis
  aks_max_cpu_node_count = 4  # maximum number of cpu nodes, should be at least aks_min_cpu_node_count
  aks_gpu_node_vm_size  = "Standard_NC4as_T4_v3"
  aks_min_gpu_node_count = 1  # minimum number of gpu nodes, can be 0 to save cost during idle but users have to manually scale it up using API call.
  aks_max_gpu_node_count = 1  # maximum number of gpu nodes, should be at least aks_min_gpu_node_count
  acr_login_server      = ""              # change this to acr where you store nxs container
  acr_username          = ""
  acr_password          = ""
  nxs_scheduler_image             = "nxsacrxxx.azurecr.io/nxs/dev" # change nxsacrxxx.azurecr.io to your acr_login_server
  nxs_scheduler_image_tag         = "v0.1.0"
  nxs_workload_manager_image      = "nxsacrxxx.azurecr.io/nxs/dev" # change nxsacrxxx.azurecr.io to your acr_login_server
  nxs_workload_manager_image_tag  = "v0.1.0"
  nxs_backend_monitor_image      = "nxsacrxxx.azurecr.io/nxs/dev" # change nxsacrxxx.azurecr.io to your acr_login_server
  nxs_backend_monitor_image_tag  = "v0.1.0"
  nxs_backend_gpu_image           = "nxsacrxxx.azurecr.io/nxs/dev" # change nxsacrxxx.azurecr.io to your acr_login_server
  nxs_backend_gpu_image_tag       = "v0.1.0"
  nxs_api_image                   = "nxsacrxxx.azurecr.io/nxs/dev" # change nxsacrxxx.azurecr.io to your acr_login_server
  nxs_api_image_tag               = "v0.1.0"  
  use_azure_redis_cache           = true                          # set to true if you want to use azure redis cache  
  az_redis_cache_capacity         = 2
  aks_max_num_api_containers      = 4                             # autoscale number of API frontend to keep up with incoming requests
}

output nxs_url {
  value = module.nxs.nxs_url
}

output nxs_api_key {
  value = module.nxs.nxs_api_key
  sensitive = true
}