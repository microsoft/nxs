provider "azurerm" {
  features {}
  subscription_id = var.base.subscription_id
  tenant_id       = var.base.tenant_id
  alias           = "user_subscription"
}

resource "azurerm_kubernetes_cluster" "nxsapp_aks" {
  provider            = azurerm.user_subscription
  name                = lower(substr("nxs-${var.base.deployment_name}-aks", 0, 24))
  location            = var.base.location
  resource_group_name = var.base.rg_name
  dns_prefix          = "nxsapp-aks"

  default_node_pool {
    name       = "cpupool1"
    enable_auto_scaling = true
    vm_size    = var.aks_cpupool1_vm_size
    min_count = var.aks_cpupool1_min_node_count    
    max_count = var.aks_cpupool1_max_node_count
    node_labels = {
      "restype" : "cpu"
    }    
  }

  identity {
    type = "SystemAssigned"
  }

  key_vault_secrets_provider {
    secret_rotation_enabled = true
    secret_rotation_interval = "2m"
  }
}

# create public ip for this aks
resource "azurerm_public_ip" "nxsapp_public_ip" {
  name                = "nxsapp-ip"
  resource_group_name = azurerm_kubernetes_cluster.nxsapp_aks.node_resource_group
  location            = var.base.location
  allocation_method   = "Static"
  sku = "Standard"

  domain_name_label = var.aks_domain_name_label
}

#output "kube_config" {
#  value = azurerm_kubernetes_cluster.nxsapp_aks.kube_config_raw
#  sensitive = true
#}

#output aks_public_ip {
#  value = azurerm_public_ip.nxsapp_public_ip.ip_address
#}

#output aks_domain_name_fqdn {
#  value = azurerm_public_ip.nxsapp_public_ip.fqdn
#}

output aks_base {
  value = {
    public_ip =  azurerm_public_ip.nxsapp_public_ip.ip_address
    domain_name_label = var.aks_domain_name_label
    domain_name_fqdn = azurerm_public_ip.nxsapp_public_ip.fqdn
    kube_config = azurerm_kubernetes_cluster.nxsapp_aks.kube_config_raw    
    tenant_id = azurerm_kubernetes_cluster.nxsapp_aks.identity[0].tenant_id
    secrets_provider_client_id = azurerm_kubernetes_cluster.nxsapp_aks.key_vault_secrets_provider[0].secret_identity[0].client_id
    secrets_provider_object_id = azurerm_kubernetes_cluster.nxsapp_aks.key_vault_secrets_provider[0].secret_identity[0].object_id
    host = azurerm_kubernetes_cluster.nxsapp_aks.kube_config.0.host
    username = azurerm_kubernetes_cluster.nxsapp_aks.kube_config.0.username
    password = azurerm_kubernetes_cluster.nxsapp_aks.kube_config.0.password
    client_certificate = azurerm_kubernetes_cluster.nxsapp_aks.kube_config.0.client_certificate
    client_key = azurerm_kubernetes_cluster.nxsapp_aks.kube_config.0.client_key
    cluster_ca_certificate = azurerm_kubernetes_cluster.nxsapp_aks.kube_config.0.cluster_ca_certificate
  }
}