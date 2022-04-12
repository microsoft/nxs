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