provider "azurerm" {
  features {}
  subscription_id = var.base.subscription_id
  tenant_id       = var.base.tenant_id
  alias           = "user_subscription"
}

resource "azurerm_kubernetes_cluster" "nxs_aks" {
  provider            = azurerm.user_subscription
  name                = lower(substr("nxs-${var.base.deployment_name}-aks", 0, 24))
  location            = var.base.location
  resource_group_name = var.base.rg_name
  dns_prefix          = "nxs-aks"
  kubernetes_version  = "1.23.12"

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

  network_profile {
    network_plugin = "azure"
    outbound_type = "managedNATGateway"
    nat_gateway_profile {
      managed_outbound_ip_count = 1
    }
  }
}

# create t4-gpu-pool
resource "azurerm_kubernetes_cluster_node_pool" "nxs_aks_gpupool1" {
  name                  = "gpupool1"  
  kubernetes_cluster_id = azurerm_kubernetes_cluster.nxs_aks.id
  enable_auto_scaling = true
  vm_size               = var.aks_gpupool1_vm_size
  min_count            = var.aks_gpupool1_min_node_count
  max_count            = var.aks_gpupool1_max_node_count
  node_labels = {
    "restype" : "gpu"
  }
}

# create random suffix to make sure public dns will be created successfully
resource "random_password" "nxs_dns_suffix" {
  length = 4
  special = false
  min_special = 0
  min_numeric = 4
  override_special = "-_?@#"
}


# create public ip for this aks
resource "azurerm_public_ip" "nxs_public_ip" {
  name                = "nxs-ip"
  resource_group_name = azurerm_kubernetes_cluster.nxs_aks.node_resource_group
  location            = var.base.location
  allocation_method   = "Static"
  sku = "Standard"

  domain_name_label = "nxs-${var.base.deployment_name}-${random_password.nxs_dns_suffix.result}"
}

output aks_info {
  value = {
    aks_id = azurerm_kubernetes_cluster.nxs_aks.id
    aks_node_resource_group = azurerm_kubernetes_cluster.nxs_aks.node_resource_group
    aks_principal_id = azurerm_kubernetes_cluster.nxs_aks.identity[0].principal_id
    aks_kubelet_object_id = azurerm_kubernetes_cluster.nxs_aks.kubelet_identity[0].object_id
    aks_host = azurerm_kubernetes_cluster.nxs_aks.kube_config.0.host
    aks_username = azurerm_kubernetes_cluster.nxs_aks.kube_config.0.username
    aks_password = azurerm_kubernetes_cluster.nxs_aks.kube_config.0.password
    aks_client_certificate = azurerm_kubernetes_cluster.nxs_aks.kube_config.0.client_certificate
    aks_client_client_key = azurerm_kubernetes_cluster.nxs_aks.kube_config.0.client_key
    aks_client_cluster_ca_certificate = azurerm_kubernetes_cluster.nxs_aks.kube_config.0.cluster_ca_certificate
    aks_tenant_id = azurerm_kubernetes_cluster.nxs_aks.identity[0].tenant_id
    aks_kv_secrets_provider_client_id = azurerm_kubernetes_cluster.nxs_aks.key_vault_secrets_provider[0].secret_identity[0].client_id
    aks_kv_secrets_provider_object_id = azurerm_kubernetes_cluster.nxs_aks.key_vault_secrets_provider[0].secret_identity[0].object_id
    aks_public_ip = azurerm_public_ip.nxs_public_ip.ip_address
    aks_domain_name_label = azurerm_public_ip.nxs_public_ip.domain_name_label
    aks_domain_name_fqdn = azurerm_public_ip.nxs_public_ip.fqdn
    aks_kube_config = azurerm_kubernetes_cluster.nxs_aks.kube_config_raw
  }
}