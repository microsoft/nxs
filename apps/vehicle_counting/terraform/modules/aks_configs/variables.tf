variable base {
    type = any
    description = "Base configuration"
}

variable aks_base {
    type = any
}

variable kv_base {
    type = any
}

variable app_namespace {
    type = string
    default = "nxsapp"
}