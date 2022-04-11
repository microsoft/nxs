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

variable aks_tenant_id {
    type = string
}

variable aks_kv_secrets_provider_client_id {
    type = string
}

variable kv_name {
    type = string
}

variable aks_public_ip_address {
    type = string
}

variable aks_domain_name_label {
    type = string
}

variable aks_domain_name_fqdn {
    type = string
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