provider "azurerm" {
  features {}
  subscription_id = var.base.subscription_id
  tenant_id       = var.base.tenant_id
  alias           = "user_subscription"
}

# create cpu-pool for apps
resource "azurerm_kubernetes_cluster_node_pool" "nxs_aks_app_cpupool1" {
  name                  = "appcpupool1"  
  kubernetes_cluster_id = var.aks_base_info.aks_id
  enable_auto_scaling = true
  vm_size               = var.aks_cpupool1_vm_size
  min_count            = var.aks_cpupool1_min_node_count
  max_count            = var.aks_cpupool1_max_node_count
  node_labels = {
    "restype" : "cpu"
  }
}

# create public ip for this aks
resource "azurerm_public_ip" "nxsapp_public_ip" {
  name                = "nxsapp-ip"
  resource_group_name = var.aks_base_info.aks_node_resource_group
  location            = var.base.location
  allocation_method   = "Static"
  sku = "Standard"

  domain_name_label = var.aks_domain_name_label
}

output aks_info {
  value = {
    public_ip =  azurerm_public_ip.nxsapp_public_ip.ip_address
    domain_name_label = var.aks_domain_name_label
    domain_name_fqdn = azurerm_public_ip.nxsapp_public_ip.fqdn

    kube_config = var.aks_base_info.aks_kube_config
    tenant_id = var.aks_base_info.aks_tenant_id
    secrets_provider_client_id = var.aks_base_info.aks_kv_secrets_provider_client_id
    secrets_provider_object_id = var.aks_base_info.aks_kv_secrets_provider_object_id
    host = var.aks_base_info.aks_host
    username = var.aks_base_info.aks_username
    password = var.aks_base_info.aks_password
    client_certificate = var.aks_base_info.aks_client_certificate
    client_key = var.aks_base_info.aks_client_client_key
    cluster_ca_certificate = var.aks_base_info.aks_client_cluster_ca_certificate
  }
}