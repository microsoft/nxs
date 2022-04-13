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
    ssl_cert_owner_email = var.ssl_cert_owner_email
    acr_login_server = var.acr_login_server
    acr_username = var.acr_username
    acr_password = var.acr_password
    nxs_url = var.nxs_url
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
  kv_base = module.keyvault.kv_base
  aks_base = module.aks.aks_base
}

module db {
  source = "../db"
  base    = local.base_config
}

module storage {
  source = "../storage"
  base    = local.base_config
}

module keyvault_secrets {
  source = "../keyvault_secrets"
  base    = local.base_config
  keyvault_id = module.keyvault.kv_base.kv_id
  secrets = {
    ApiKey = module.apikey.apikey
    MongoDbConnectionStr = module.db.db_base.db_conn_str
    MongoDbMaindbName = module.db.db_base.db_name
    BlobstoreConnectionStr = module.storage.storage_base.connection_string
    BlobstoreContainerName = module.storage.storage_base.container_name    
    NxsUrl = var.nxs_url
    NxsApiKey = var.nxs_api_key
    AksKubeConfig = module.aks.aks_base.kube_config
    AppUrl = module.aks.aks_base.domain_name_fqdn
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
  kv_base = module.keyvault.kv_base
  aks_base = module.aks.aks_base
}

module aks_deployments {
  source = "../aks_deployments"
  base    = local.base_config
  aks_base = module.aks.aks_base
  aks_configs_completed = module.aks_configs.aks_configs_completed  
}