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

locals {
  base_config = {
    rg_name = var.rg_name    
    deployment_name = var.deployment_name
    subscription_id = var.subscription_id
    tenant_id = var.tenant_id
    location = var.location      
    admin_group_object_id = var.admin_group_object_id
    ssl_cert_owner_email = var.ssl_cert_owner_email
    acr_login_server = var.acr_login_server
    acr_username = var.acr_username
    acr_password = var.acr_password
    nxs_api_key = var.nxs_api_key
    nxsapp_api_container = var.nxsapp_api_container
    nxsapp_worker_container = var.nxsapp_worker_container
    nxs_detector_uuid = var.nxs_detector_uuid
    nxs_tracker_uuid = var.nxs_tracker_uuid
  }
}

module apikey {
  source = "../apikey"  
}

module aks {
    source = "../aks"
    base    = local.base_config
    aks_base_info = var.aks_base_info
    aks_domain_name_label = var.api_domain_name_label
    aks_cpupool1_vm_size = var.aks_cpu_node_vm_size
    aks_cpupool1_min_node_count = var.aks_min_cpu_node_count
    aks_cpupool1_max_node_count = var.aks_max_cpu_node_count
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
}

module storage {
  source = "../storage"
  base    = local.base_config
  data_retention_days = var.data_retention_days
  delete_snapshot_retention_days = var.delete_snapshot_retention_days
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
    NxsUrl = "nxs-api-servers-svc.nxs"
    NxsApiKey = var.nxs_api_key
    AksKubeConfig = module.aks.aks_info.kube_config
    AppUrl = module.aks.aks_info.domain_name_fqdn
    AppSwaggerUrl = "${module.aks.aks_info.domain_name_fqdn}/docs"
    AppApiContainer = var.nxsapp_api_container
    AppWorkerContainer = var.nxsapp_worker_container
    AppReportCountsInterval = var.app_report_counts_interval
    NxsDetectorUUID = var.nxs_detector_uuid
    NxsTrackerUUID = var.nxs_tracker_uuid    
  }
}

module aks_configs {  
  source = "../aks_configs"
  base    = local.base_config
  keyvault_info = module.keyvault.keyvault_info
  aks_info = module.aks.aks_info
}

module aks_deployments {
  source = "../aks_deployments"
  base    = local.base_config
  aks_info = module.aks.aks_info
  aks_configs_info = module.aks_configs.aks_configs_info
  kv_store_secrets_info = module.keyvault_secrets.kv_store_secrets_info
}