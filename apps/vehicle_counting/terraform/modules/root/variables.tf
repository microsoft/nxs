# Required configurations
variable subscription_id {
  type        = string
  description = "Azure subscription id"
}

variable tenant_id {
  type        = string
  description = "Azure tenant id"
}

variable deployment_name {
  type = string
  description = "Name of deployment"
}

variable location {
  type        = string
  description = "Location of the resource group"
}

variable rg_name {
  type        = string
  description = "Name of the resource group"
}

variable admin_group_object_id {
  type        = string
  description = "Object ID of the Pixie admin group"
}

variable ssl_cert_owner_email {
  type        = string
  description = "email used to register ssl certificate"
}

variable acr_login_server {
  type = string
  description = "Azure container registry server"
}

variable acr_username {
  type = string
  description = "Username to access azure container registry"
}

variable acr_password {
  type = string
  description = "Password to access azure container registry"
}

variable api_domain_name_label {
  type = string
  description = "prefix name used in API URL."
}

variable nxs_url {
  type = string
  description = "URL to NXS cluster"
}

variable nxs_api_key {
  type = string
  description = "Api key to access NXS cluster"
}

variable nxsapp_api_container {
  type = string
  description = "Location of api container in acr, e.g., ossnxs.azurecr.io/vcapi:v0.1"
}

variable nxsapp_worker_container {
  type = string
  description = "Location of worker container in acr, e.g., ossnxs.azurecr.io/vcworker:v0.1"
}

variable nxs_detector_uuid {
  type = string
  description = "UUID of object detector"
  default = "bbff897256c9431eb19a2ad311749b39"
}

variable nxs_tracker_uuid {
  type = string
  description = "UUID of tracker"
  default = "451ffc2ee1594fe2a6ace17fca5117ab"
}

variable app_report_counts_interval {
  type = number
  default = 900
}

### Optional configurations ###

variable aks_cpu_node_vm_size {
  type = string
  description = "vm size for cpu nodes"
  default = "Standard_D2s_v4"
}

variable aks_min_cpu_node_count {
  type = number
  description = "Minimum number of CPUs nodes to be used in NXS for scheduler, workload manager, api servers and cpu inference nodes."
  default     = 1
}

variable aks_max_cpu_node_count {
  type = number
  description = "Maximum number of CPUs nodes to be used in NXS for scheduler, workload manager, api servers and cpu inference nodes."
  default     = 3
}

variable data_retention_days {
    type = number
    default = 18
}

variable data_delete_snapshot_retention_days {
    type = number
    default = 3
}
