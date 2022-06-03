variable base {
    type = any
    description = "Base configuration"
}

variable aks_info {
    type = any
    description = "aks output"
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