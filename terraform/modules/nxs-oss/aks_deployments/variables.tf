variable base {
    type = any
    description = "Base configuration"
}

variable aks_host {
    type = string
}

variable aks_username {
    type = string
}

variable aks_password {
    type = string
}

variable aks_client_certificate {
    type = string
}

variable aks_client_client_key {
    type = string
}

variable aks_client_cluster_ca_certificate {
    type = string
}

variable aks_configs_completed {
    type = bool
}

variable nxs_api_image {
    type = string
    default = "ossnxs.azurecr.io/nxs/dev"
}
variable nxs_api_image_tag {
    type = string
    default = "v0.1.0"
}
variable nxs_api_cpu_requests {
    type = string
    default = "1000m"
}
variable nxs_api_memory_requests {
    type = string
    default = "2Gi"
}
variable nxs_api_num_replicas {
    type = number
    default = 1
}
variable enable_api_v1 {
  type = bool
  description = "Enable api v1 for Pixie"
  default     = true
}

variable nxs_scheduler_image {
    type = string
    default = "ossnxs.azurecr.io/nxs/dev"
}
variable nxs_scheduler_image_tag {
    type = string
    default = "v0.1.0"
}
variable nxs_scheduler_cpu_requests {
    type = string
    default = "250m"
}
variable nxs_scheduler_memory_requests {
    type = string
    default = "0.5Gi"
}

variable nxs_workload_manager_image {
    type = string
    default = "ossnxs.azurecr.io/nxs/dev"
}
variable nxs_workload_manager_image_tag {
    type = string
    default = "v0.1.0"
}
variable nxs_workload_manager_cpu_requests {
    type = string
    default = "250m"
}
variable nxs_workload_manager_memory_requests {
    type = string
    default = "0.5Gi"
}

variable nxs_backend_gpu_image {
    type = string
    default = "ossnxs.azurecr.io/nxs/dev"
}
variable nxs_backend_gpu_image_tag {
    type = string
    default = "v0.1.0"
}
variable nxs_backend_gpu_cpu_requests {
    type = string
    default = "3000m"
}
variable nxs_backend_gpu_memory_requests {
    type = string
    default = "16Gi"
}
variable nxs_backend_gpu_num_replicas {
    type = number
    default = 1
}