variable base {
    type = any
    description = "Base configuration"
}

variable aks_info {
    type = any
}

variable keyvault_info {
    type = any
}

variable app_namespace {
    type = string
    default = "nxsapp"
}