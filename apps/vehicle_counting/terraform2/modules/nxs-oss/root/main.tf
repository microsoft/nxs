# configure providers
terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
      version = ">= 2.96"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = ">=2.18.0"
    }
    kubernetes = {
      source = "hashicorp/kubernetes"
      version = ">= 2.8.0"
    }    
  }
}

provider "azurerm" {
  features {}
  tenant_id = var.tenant_id
  subscription_id = var.subscription_id
}

module rg {
    source  = "../rg"
    name    = var.rg_name
    location = var.location
    admin_group_object_id = var.admin_group_object_id
    tenant_id = var.tenant_id
    subscription_id = var.subscription_id
}

locals {
  base_config = {
    deployment_name = var.deployment_name
    subscription_id = var.subscription_id
    tenant_id = var.tenant_id
    location = var.location
    rg_name = module.rg.rg_info.name
    admin_group_object_id = var.admin_group_object_id
  }
}

module aks {
  source = "../aks"
  base    = local.base_config  
  aks_cpupool1_vm_size = var.aks_cpu_node_vm_size
  aks_cpupool1_min_node_count = var.aks_min_cpu_node_count
  aks_cpupool1_max_node_count = var.aks_max_cpu_node_count
  aks_gpupool1_vm_size = var.aks_gpu_node_vm_size
  aks_gpupool1_min_node_count = var.aks_min_gpu_node_count
  aks_gpupool1_max_node_count = var.aks_max_gpu_node_count
}

module db {
  source = "../db"
  base    = local.base_config
  db_autoscale_max_throughput = var.db_autoscale_max_throughput
}

module storage {
  source = "../storage"
  base    = local.base_config
}

module keyvault {
  source = "../keyvault"
  base    = local.base_config
}

module apikey {
  source = "../apikey"  
}

# this module uses azure redis cache
module azure_redis {
  source = "../redis_cache"
  base    = local.base_config
  az_redis_cache_family_type = var.az_redis_cache_family_type
  az_redis_cache_capacity = var.az_redis_cache_capacity
  az_redis_cache_sku = var.az_redis_cache_sku
  create_module = var.use_azure_redis_cache
}

# this module deploys oss redis into our aks cluster
module oss_redis {
  source = "../redis_oss"
  base    = local.base_config
  aks_info = module.aks.aks_info
  create_module = !var.use_azure_redis_cache
}

module keyvault_acl {
  source = "../keyvault_acl"
  base    = local.base_config
  keyvault_info = module.keyvault.keyvault_info
  aks_info = module.aks.aks_info
}

module keyvault_secrets {
  source = "../keyvault_secrets"
  base    = local.base_config
  keyvault_id = module.keyvault.kv_id
  secrets = {
    ApiKey = module.apikey.apikey
    MongoDbConnectionStr = module.db.db_info.nxs_mongodb_conn_str
    MongoDbMaindbName = module.db.db_info.nxs_mongodb_maindb_name
    BlobstoreConnectionStr = module.storage.storage_info.nxs_storage_connection_string
    BlobstoreContainerName = module.storage.storage_info.nxs_storage_container_name
    RedisAddress = var.use_azure_redis_cache ? module.azure_redis.redis_info.redis_address : module.oss_redis.redis_info.redis_address
    RedisPort = var.use_azure_redis_cache ? module.azure_redis.redis_info.redis_port : module.oss_redis.redis_info.redis_port
    RedisPassword = var.use_azure_redis_cache ? module.azure_redis.redis_info.redis_password : module.oss_redis.redis_info.redis_password
    RedisUseSSL = var.use_azure_redis_cache ? module.azure_redis.redis_info.redis_use_ssl : module.oss_redis.redis_info.redis_use_ssl
    NxsUrl = "https://${module.aks.aks_info.aks_domain_name_fqdn}"
    NxsSwaggerUrl = "https://${module.aks.aks_info.aks_domain_name_fqdn}/docs"
    AksKubeConfig = module.aks.aks_info.aks_kube_config
  }
}

module aks_configs {  
  source = "../aks_configs"
  base    = local.base_config
  aks_info = module.aks.aks_info
  keyvault_info = module.keyvault.keyvault_info
  redis_info = var.use_azure_redis_cache ? module.azure_redis.redis_info : module.oss_redis.redis_info
  ssl_cert_owner_email = var.ssl_cert_owner_email
  acr_login_server = var.acr_login_server
  acr_user_name = var.acr_username
  acr_password = var.acr_password
}

module aks_deployments {
  source = "../aks_deployments"
  base    = local.base_config
  aks_info = module.aks.aks_info
  aks_configs_info = module.aks_configs.aks_configs_info
  enable_api_v1 = var.enable_api_v1
  nxs_backend_gpu_num_replicas = var.aks_min_gpu_node_count
  nxs_api_min_num_replicas = var.aks_min_num_api_containers
  nxs_api_max_num_replicas = var.aks_max_num_api_containers  
  nxs_scheduler_image = var.nxs_scheduler_image
  nxs_scheduler_image_tag = var.nxs_scheduler_image_tag
  nxs_workload_manager_image = var.nxs_workload_manager_image
  nxs_workload_manager_image_tag = var.nxs_workload_manager_image_tag
  nxs_backend_monitor_image = var.nxs_backend_monitor_image
  nxs_backend_monitor_image_tag = var.nxs_backend_monitor_image_tag
  nxs_backend_gpu_image = var.nxs_backend_gpu_image
  nxs_backend_gpu_image_tag = var.nxs_backend_gpu_image_tag
  nxs_api_image = var.nxs_api_image
  nxs_api_image_tag = var.nxs_api_image_tag
  run_initializer = var.run_initializer
  nxs_initializer_image = var.nxs_initializer_image
  nxs_initializer_image_tag = var.nxs_initializer_image_tag
}

output nxs_url {
  value = "https://${module.aks.aks_info.aks_domain_name_fqdn}"
}

output nxs_api_key {
  value = module.apikey.apikey
  sensitive = true
}

output nxs_info {
  value = {
    nxs_api_key = module.apikey.apikey
    rg_info = module.rg.rg_info
    aks_info = module.aks.aks_info
  }
}