# Required configurations
variable base {
  type        = any
  description = "Azure base information"
}

variable app_config {
  type        = any
  description = "Azure base information"
}

variable aks_base_info {
  type = any
  description = "nxs aks info"
}

variable aks_deployments_base_info {
  type = any
  description = "nxs aks deployments info"
}

variable aks_configs_base_info {
  type = any
  description = "nxs aks_configs info"
}

variable nxs_api_key {
  type = string
  description = "Api key to access NXS cluster"
}
