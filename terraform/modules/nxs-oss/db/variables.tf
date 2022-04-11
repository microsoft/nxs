variable base {
    type = any
    description = "Base configuration"
}

variable db_autoscale_max_throughput {
    type        = number
    description = "Max throughput"
    default     = 4000
}