variable base {
    type = any
    description = "Base configuration"
}

variable aks_cpupool1_vm_size {
    type = string
    default = "Standard_D2s_v4"
}

variable aks_cpupool1_node_count {
    type = number
    default = 3
}

variable aks_gpupool1_vm_size {
    type = string
    default = "Standard_NC4as_T4_v3"
}

variable aks_gpupool1_node_count {
    type = number
    default = 1
}