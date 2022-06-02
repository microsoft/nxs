variable base {
    type = any
    description = "Base configuration"
}

variable aks_info {
    type = any
    description = "aks output"
}

variable redis_info {
    type = any
    description = "redis output"
}

variable keyvault_info {
    type = any
    description = "keyvault output"
}

variable ssl_cert_owner_email {
    type = string
}

variable acr_login_server {
    type = string
}

variable acr_user_name {
    type = string
}

variable acr_password {
    type = string
}

variable nginx_min_replicas {
    type = number
    default = 2
}

variable nginx_max_replicas {
    type = number
    default = 8
}