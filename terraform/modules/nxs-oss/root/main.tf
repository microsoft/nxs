# configure providers
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 2.96"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = ">=2.18.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.8.0"
    }
  }
}

provider "azurerm" {
  features {}
  tenant_id       = var.base.tenant_id
  subscription_id = var.base.subscription_id
}

# module rg {
#   source                      = "../rg"
#   name                        = var.base.deployment_name
#   location                    = var.base.location
#   admin_group_object_id       = var.base.admin_group_object_id
#   tenant_id                   = var.base.tenant_id
#   subscription_id             = var.base.subscription_id
# }

module "rg" {
  source                = "../rg"
  name                  = var.rg_name
  location              = var.location
  admin_group_object_id = var.admin_group_object_id
  tenant_id             = var.tenant_id
  subscription_id       = var.subscription_id
}

locals {
  base_config = {
    deployment_name       = var.base.deployment_name
    rg_name               = module.rg.rg_info.name
    subscription_id       = var.base.subscription_id
    tenant_id             = var.base.tenant_id
    location              = var.base.location
    admin_group_object_id = var.base.admin_group_object_id
  }
}

module "aks" {
  source                      = "../aks"
  base                        = local.base_config
  aks_cpupool1_vm_size        = var.nxs_config.aks.aks_cpu_node_vm_size
  aks_cpupool1_min_node_count = var.nxs_config.aks.aks_min_cpu_node_count
  aks_cpupool1_max_node_count = var.nxs_config.aks.aks_max_cpu_node_count
  aks_gpupool1_vm_size        = var.nxs_config.aks.aks_gpu_node_vm_size
  aks_gpupool1_min_node_count = var.nxs_config.aks.aks_min_gpu_node_count
  aks_gpupool1_max_node_count = var.nxs_config.aks.aks_max_gpu_node_count
}

module "db" {
  source                      = "../db"
  base                        = local.base_config
  db_autoscale_max_throughput = var.nxs_config.db.db_autoscale_max_throughput
}

module "storage" {
  source = "../storage"
  base   = local.base_config
}

module "keyvault" {
  source = "../keyvault"
  base   = local.base_config
}

module "apikey" {
  source = "../apikey"
}

# this module uses azure redis cache
module "azure_redis" {
  source                     = "../redis_cache"
  base                       = local.base_config
  az_redis_cache_sku         = var.nxs_config.redis.azure_redis_cache.azure_redis_cache_sku
  az_redis_cache_family_type = var.nxs_config.redis.azure_redis_cache.azure_redis_cache_family_type
  az_redis_cache_capacity    = var.nxs_config.redis.azure_redis_cache.azure_redis_cache_capacity
  create_module              = var.nxs_config.redis.use_azure_redis_cache
}

# this module deploys oss redis into our aks cluster
module "redis" {
  source        = "../redis_oss"
  base          = local.base_config
  aks_info      = module.aks.aks_info
  create_module = !var.nxs_config.redis.use_azure_redis_cache
}

module "keyvault_acl" {
  source        = "../keyvault_acl"
  base          = local.base_config
  keyvault_info = module.keyvault.keyvault_info
  aks_info      = module.aks.aks_info
}

module "keyvault_secrets" {
  source      = "../keyvault_secrets"
  base        = local.base_config
  keyvault_id = module.keyvault.kv_id
  secrets = {
    ApiKey                 = module.apikey.apikey
    MongoDbConnectionStr   = module.db.db_info.nxs_mongodb_conn_str
    MongoDbMaindbName      = module.db.db_info.nxs_mongodb_maindb_name
    BlobstoreConnectionStr = module.storage.storage_info.nxs_storage_connection_string
    BlobstoreContainerName = module.storage.storage_info.nxs_storage_container_name
    RedisAddress           = var.nxs_config.redis.use_azure_redis_cache ? module.azure_redis.redis_info.redis_address : module.redis.redis_info.redis_address
    RedisPort              = var.nxs_config.redis.use_azure_redis_cache ? module.azure_redis.redis_info.redis_port : module.redis.redis_info.redis_port
    RedisPassword          = var.nxs_config.redis.use_azure_redis_cache ? module.azure_redis.redis_info.redis_password : module.redis.redis_info.redis_password
    RedisUseSSL            = var.nxs_config.redis.use_azure_redis_cache ? module.azure_redis.redis_info.redis_use_ssl : module.redis.redis_info.redis_use_ssl
    NxsUrl                 = "https://${module.aks.aks_info.aks_domain_name_fqdn}"
    NxsSwaggerUrl          = "https://${module.aks.aks_info.aks_domain_name_fqdn}/docs"
    AksKubeConfig          = module.aks.aks_info.aks_kube_config
  }
}

module "aks_configs" {
  source               = "../aks_configs"
  base                 = local.base_config
  aks_info             = module.aks.aks_info
  keyvault_info        = module.keyvault.keyvault_info
  redis_info           = var.nxs_config.redis.use_azure_redis_cache ? module.azure_redis.redis_info : module.redis.redis_info
  ssl_cert_owner_email = var.base.ssl_cert_owner_email
  acr_login_server     = var.nxs_config.acr.acr_login_server
  acr_user_name        = var.nxs_config.acr.acr_username
  acr_password         = var.nxs_config.acr.acr_password
}

module "aks_deployments" {
  source           = "../aks_deployments"
  base             = local.base_config
  aks_info         = module.aks.aks_info
  aks_configs_info = module.aks_configs.aks_configs_info

  nxs_backend_gpu_num_replicas = var.nxs_config.aks.aks_min_gpu_node_count
  nxs_api_min_num_replicas     = var.nxs_config.containers.frontend.min_num_frontend_replicas
  nxs_api_max_num_replicas     = var.nxs_config.containers.frontend.max_num_frontend_replicas

  nxs_scheduler_image     = var.nxs_config.containers.scheduler.nxs_scheduler_image
  nxs_scheduler_image_tag = var.nxs_config.containers.scheduler.nxs_scheduler_image_tag

  nxs_workload_manager_image     = var.nxs_config.containers.workload_manager.nxs_workload_manager_image
  nxs_workload_manager_image_tag = var.nxs_config.containers.workload_manager.nxs_workload_manager_image_tag

  nxs_backend_monitor_image     = var.nxs_config.containers.backend_monitor.nxs_backend_monitor_image
  nxs_backend_monitor_image_tag = var.nxs_config.containers.backend_monitor.nxs_backend_monitor_image_tag

  nxs_backend_gpu_image     = var.nxs_config.containers.backend_gpu.nxs_backend_gpu_image
  nxs_backend_gpu_image_tag = var.nxs_config.containers.backend_gpu.nxs_backend_gpu_image_tag

  nxs_api_image     = var.nxs_config.containers.frontend.nxs_api_image
  nxs_api_image_tag = var.nxs_config.containers.frontend.nxs_api_image_tag
  enable_api_v1     = var.nxs_config.containers.frontend.enable_api_v1

  run_initializer           = var.nxs_config.containers.model_initializer.run_initializer
  nxs_initializer_image     = var.nxs_config.containers.model_initializer.nxs_initializer_image
  nxs_initializer_image_tag = var.nxs_config.containers.model_initializer.nxs_initializer_image_tag
}

output "nxs_url" {
  value = "https://${module.aks.aks_info.aks_domain_name_fqdn}"
}

output "nxs_api_key" {
  value     = module.apikey.apikey
  sensitive = true
}

output "nxs_info" {
  value = {
    nxs_api_key          = module.apikey.apikey
    rg_info              = module.rg.rg_info
    aks_info             = module.aks.aks_info
    aks_configs_info     = module.aks_configs.aks_configs_info
    aks_deployments_info = module.aks_deployments.aks_deployments_info
  }
}
