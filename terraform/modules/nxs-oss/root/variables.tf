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

### Optional configurations ###

# redis configurations
variable az_redis_cache_family_type {
  type        = string
  description = "Azure Redis Cache Family Type"
  default     = "C"
}

variable az_redis_cache_capacity {
  type        = number
  description = "Azure Redis Cache Capacity Type"
  default     = 1
}

variable az_redis_cache_sku {
  type        = string
  description = "Azure Redis Cache SKU Type"
  default     = "Standard"
}

variable db_autoscale_max_throughput {
  type        = number
  description = "Max throughput"
  default     = 4000
}

variable aks_cpu_node_vm_size {
  type = string
  description = "vm size for cpu nodes"
  default = "Standard_D2s_v4"
}

variable aks_min_cpu_node_count {
  type = number
  description = "Minimum number of CPUs nodes to be used in NXS for scheduler, workload manager, api servers and cpu inference nodes."
  default     = 3
}

variable aks_max_cpu_node_count {
  type = number
  description = "Maximum number of CPUs nodes to be used in NXS for scheduler, workload manager, api servers and cpu inference nodes."
  default     = 3
}

variable aks_gpu_node_vm_size {
  type = string
  description = "vm size for gpu nodes"
  default = "Standard_NC4as_T4_v3"
}

variable aks_min_gpu_node_count {
  type = number
  description = "Min Number of GPUs to be used in NXS"
  default     = 1
}

variable aks_max_gpu_node_count {
  type = number
  description = "Max Number of GPUs to be used in NXS"
  default     = 1
}

variable aks_num_api_containers {
  type = number
  description = "Number of replicas of api servers"
  default     = 1
}

variable enable_api_v1 {
  type = bool
  description = "Enable api v1 for Pixie"
  default     = true
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