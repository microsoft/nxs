variable base {
    type = any
    description = "Base configuration"
}

variable db_autoscale_max_throughput {
    type        = number
    description = "Max throughput"
    default     = 4000
}

variable db_item_ttl {
    type        = number
    description = "Time to keep items in seconds. Set to positive number to automatically delete items after TTL."
    default     = -1
}