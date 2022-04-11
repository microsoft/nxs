variable base {
    type = any
    description = "Base configuration"
}

variable keyvault_id {
    type = string
}

#variable current_tenant_id {
#    type = string
#}

#variable current_object_id {
#    type = string
#}

# aks info
variable aks_tenant_id {
    type = string
}

variable aks_principal_id {
    type = string
}

#variable aks_kubelet_object_id {
#    type = string
#}

#variable aks_kv_secrets_provider_client_id {
#    type = string
#}

variable aks_kv_secrets_provider_object_id {
    type = string
}