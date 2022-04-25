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

variable redis_cpu_per_node {
  type        = string
  description = "Cpu allocated to single node in redis cluster"
  default     = "1000m"
}

variable redis_memory_per_node {
  type        = string
  description = "Memory allocated to single node in redis cluster"
  default     = "2Gi"
}

variable create_module {
  type = bool
  description = "Enable or disable this module"
}