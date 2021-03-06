variable base {
    type = any
    description = "Base configuration"
}

variable aks_info {
    type = any
    description = "aks output"
}

variable aks_configs_info {
    type = any
    description = "aks_configs output"
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
    default = "750m"
}
variable nxs_api_memory_requests {
    type = string
    default = "1.5Gi"
}
variable nxs_api_min_num_replicas {
    type = number
    default = 1
}
variable nxs_api_max_num_replicas {
    type = number
    default = 4
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

variable nxs_backend_monitor_image {
    type = string
    default = "ossnxs.azurecr.io/nxs/dev"
}
variable nxs_backend_monitor_image_tag {
    type = string
    default = "v0.1.0"
}
variable nxs_backend_monitor_cpu_requests {
    type = string
    default = "250m"
}
variable nxs_backend_monitor_memory_requests {
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

variable nxs_initializer_image {
    type = string
    default = ""
}
variable nxs_initializer_image_tag {
    type = string
    default = "v0.5.0"
}

variable run_initializer {
  type = bool
  description = "Run initializer if required"
  default = false
}