variable base {
    type = any
    description = "Base configuration"
}

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