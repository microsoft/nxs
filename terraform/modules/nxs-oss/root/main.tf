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
    rg_name = module.rg.name        
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
#module redis {
#  source = "../redis_cache"
#  base    = local.base_config
#  az_redis_cache_family_type = var.az_redis_cache_family_type
#  az_redis_cache_capacity = var.az_redis_cache_capacity
#  az_redis_cache_sku = var.az_redis_cache_sku
#}

# this module deploys oss redis into our aks cluster
module redis {
  source = "../redis_oss"
  base    = local.base_config
  aks_host = module.aks.aks_host
  aks_username = module.aks.aks_username
  aks_password = module.aks.aks_password
  aks_client_certificate = module.aks.aks_client_certificate
  aks_client_client_key = module.aks.aks_client_client_key
  aks_client_cluster_ca_certificate = module.aks.aks_client_cluster_ca_certificate
}

module keyvault_acl {
  source = "../keyvault_acl"
  base    = local.base_config
  keyvault_id = module.keyvault.kv_id
  #current_tenant_id = var.tenant_id
  #current_object_id = data.azurerm_client_config.current.object_id
  aks_tenant_id = module.aks.aks_tenant_id
  aks_principal_id = module.aks.aks_principal_id
  #aks_kubelet_object_id = module.aks.aks_kubelet_object_id
  #aks_kv_secrets_provider_client_id = module.aks.aks_kv_secrets_provider_client_id
  aks_kv_secrets_provider_object_id = module.aks.aks_kv_secrets_provider_object_id
}

module keyvault_secrets {
  source = "../keyvault_secrets"
  base    = local.base_config
  keyvault_id = module.keyvault.kv_id
  secrets = {
    ApiKey = module.apikey.apikey
    MongoDbConnectionStr = module.db.nxs_mongodb_conn_str
    MongoDbMaindbName = module.db.nxs_mongodb_maindb_name
    BlobstoreConnectionStr = module.storage.nxs_storage_connection_string
    BlobstoreContainerName = module.storage.nxs_storage_container_name
    RedisAddress = module.redis.redis_address
    RedisPort = module.redis.redis_port
    RedisPassword = module.redis.redis_password
    RedisUseSSL = module.redis.redis_use_ssl
    NxsUrl = "https://${module.aks.aks_domain_name_fqdn}"
    NxsSwaggerUrl = "https://${module.aks.aks_domain_name_fqdn}/docs"
  }
}

module aks_configs {  
  source = "../aks_configs"
  base    = local.base_config
  aks_host = module.aks.aks_host
  aks_username = module.aks.aks_username
  aks_password = module.aks.aks_password
  aks_client_certificate = module.aks.aks_client_certificate
  aks_client_client_key = module.aks.aks_client_client_key
  aks_client_cluster_ca_certificate = module.aks.aks_client_cluster_ca_certificate
  aks_tenant_id = module.aks.aks_tenant_id
  aks_kv_secrets_provider_client_id = module.aks.aks_kv_secrets_provider_client_id
  kv_name = module.keyvault.kv_name
  aks_public_ip_address = module.aks.aks_public_ip
  aks_domain_name_label = module.aks.aks_domain_name_label
  ssl_cert_owner_email = var.ssl_cert_owner_email
  aks_domain_name_fqdn = module.aks.aks_domain_name_fqdn
  acr_login_server = var.acr_login_server
  acr_user_name = var.acr_username
  acr_password = var.acr_password
}

module aks_deployments {
  source = "../aks_deployments"
  base    = local.base_config
  aks_host = module.aks.aks_host
  aks_username = module.aks.aks_username
  aks_password = module.aks.aks_password
  aks_client_certificate = module.aks.aks_client_certificate
  aks_client_client_key = module.aks.aks_client_client_key
  aks_client_cluster_ca_certificate = module.aks.aks_client_cluster_ca_certificate
  aks_configs_completed = module.aks_configs.aks_configs_completed
  nxs_backend_gpu_num_replicas = var.aks_min_gpu_node_count
  nxs_api_num_replicas = var.aks_num_api_containers
  enable_api_v1 = var.enable_api_v1
}

output nxs_url {
  value = "https://${module.aks.aks_domain_name_fqdn}"
}

output nxs_api_key {
  value = module.apikey.apikey
  sensitive = true
}