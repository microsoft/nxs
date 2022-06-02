variable base {
    type = any
    description = "Base configuration"
}

variable data_retention_days {
    type = number
    default = 18
}

variable delete_snapshot_retention_days {
    type = number
    default = 3
}
