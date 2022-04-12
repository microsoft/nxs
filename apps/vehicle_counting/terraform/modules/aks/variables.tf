variable base {
    type = any
    description = "Base configuration"
}

variable aks_cpupool1_vm_size {
    type = string
    default = "Standard_D2s_v4"
}

variable aks_cpupool1_min_node_count {
    type = number
    default = 1
}

variable aks_cpupool1_max_node_count {
    type = number
    default = 4
}

variable aks_domain_name_label {
    type = string
    description = "Domain name label of this deployment, without the .<location>.cloudapp.azure.com"
}