variable base {
    type = any
    description = "Base configuration"
}

variable data_retention_days {
    type = number
    default = 18
}

variable data_delete_snapshot_retention_days {
    type = number
    default = 3
}
