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
  tenant_id = var.base.tenant_id
  subscription_id = var.base.subscription_id
}

locals {
  base_config = {
    rg_name = var.base.deployment_name
    deployment_name = var.base.deployment_name
    subscription_id = var.base.subscription_id
    tenant_id = var.base.tenant_id
    location = var.base.location      
    admin_group_object_id = var.base.admin_group_object_id
    ssl_cert_owner_email = var.base.ssl_cert_owner_email
    acr_login_server = var.app_config.acr.acr_login_server
    acr_username = var.app_config.acr.acr_username
    acr_password = var.app_config.acr.acr_password
    nxs_api_key = var.nxs_api_key
    nxsapp_api_container = "${var.app_config.containers.app_frontend.nxsapp_api_image}:${var.app_config.containers.app_frontend.nxsapp_api_tag}"
    nxsapp_worker_container = "${var.app_config.containers.app_worker.nxsapp_worker_image}:${var.app_config.containers.app_worker.nxsapp_worker_tag}"
    nxs_detector_uuid = var.app_config.app.detector_uuid
    nxs_tracker_uuid = var.app_config.app.tracker_uuid
  }
}

module apikey {
  source = "../apikey"  
}

module aks {
  source = "../aks"
  base                        = local.base_config
  aks_base_info               = var.aks_base_info
  aks_deployments_base_info   = var.aks_deployments_base_info
  aks_cpupool1_vm_size        = var.app_config.aks.aks_app_cpu_pool_vm_size
  aks_cpupool1_min_node_count = var.app_config.aks.aks_app_cpu_pool_min_node_count
  aks_cpupool1_max_node_count = var.app_config.aks.aks_app_cpu_pool_max_node_count
}

module keyvault {
  source = "../keyvault"
  base    = local.base_config
}

module keyvault_acl {
  source = "../keyvault_acl"
  base    = local.base_config
  keyvault_info = module.keyvault.keyvault_info
  aks_info = module.aks.aks_info
}

module db {
  source = "../db"
  base    = local.base_config
  db_autoscale_max_throughput = var.app_config.db.db_autoscale_max_throughput
  db_item_ttl                 = var.app_config.db.db_item_ttl
}

module storage {
  source = "../storage"
  base    = local.base_config
  data_retention_days             = var.app_config.storage.data_retention_days
  delete_snapshot_retention_days  = var.app_config.storage.delete_snapshot_retention_days
}

module keyvault_secrets {
  source = "../keyvault_secrets"
  base    = local.base_config
  keyvault_id = module.keyvault.keyvault_info.kv_id
  secrets = {
    ApiKey = module.apikey.apikey
    MongoDbConnectionStr = module.db.db_info.db_conn_str
    MongoDbMaindbName = module.db.db_info.db_name
    BlobstoreConnectionStr = module.storage.storage_info.connection_string
    BlobstoreContainerName = module.storage.storage_info.container_name    
    NxsUrl = "http://nxs-api-servers-svc.nxs"
    NxsApiKey = var.nxs_api_key
    AksKubeConfig = module.aks.aks_info.kube_config
    AppUrl = "https://${module.aks.aks_info.domain_name_fqdn}"
    AppSwaggerUrl = "https://${module.aks.aks_info.domain_name_fqdn}/docs"
    AppApiContainer = local.base_config.nxsapp_api_container
    AppWorkerContainer = local.base_config.nxsapp_worker_container
    AppReportCountsInterval = var.app_config.app.app_report_counts_interval
    NxsDetectorUUID = var.app_config.app.detector_uuid
    NxsTrackerUUID = var.app_config.app.tracker_uuid
  }
}

module aks_configs {  
  source = "../aks_configs"
  base    = local.base_config
  keyvault_info = module.keyvault.keyvault_info
  aks_info = module.aks.aks_info
  nxs_aks_configs_info = var.aks_configs_base_info
}

module aks_deployments {
  source = "../aks_deployments"
  base    = local.base_config
  aks_info = module.aks.aks_info
  aks_configs_info = module.aks_configs.aks_configs_info
  kv_store_secrets_info = module.keyvault_secrets.kv_store_secrets_info
}

output nxsapp_url {
  value = "https://${module.aks.aks_info.domain_name_fqdn}"
}