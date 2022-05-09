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
  kubernetes_version  = "1.21.9"

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

  #addon_profile {
  #  azure_keyvault_secrets_provider {
  #    enabled = true
  #    secret_rotation_enabled = true
  #  }
  #}

  key_vault_secrets_provider {
    secret_rotation_enabled = true
    secret_rotation_interval = "2m"
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

output aks_principal_id {
  value = azurerm_kubernetes_cluster.nxs_aks.identity[0].principal_id
  depends_on = [azurerm_kubernetes_cluster_node_pool.nxs_aks_gpupool1, azurerm_public_ip.nxs_public_ip]
}

output aks_kubelet_object_id {
  value = azurerm_kubernetes_cluster.nxs_aks.kubelet_identity[0].object_id
  depends_on = [azurerm_kubernetes_cluster_node_pool.nxs_aks_gpupool1, azurerm_public_ip.nxs_public_ip]
}

output aks_host {
  value = azurerm_kubernetes_cluster.nxs_aks.kube_config.0.host
  depends_on = [azurerm_kubernetes_cluster_node_pool.nxs_aks_gpupool1, azurerm_public_ip.nxs_public_ip]
}

output aks_username {
  value = azurerm_kubernetes_cluster.nxs_aks.kube_config.0.username
  depends_on = [azurerm_kubernetes_cluster_node_pool.nxs_aks_gpupool1, azurerm_public_ip.nxs_public_ip]
}

output aks_password {
  value = azurerm_kubernetes_cluster.nxs_aks.kube_config.0.password
  depends_on = [azurerm_kubernetes_cluster_node_pool.nxs_aks_gpupool1, azurerm_public_ip.nxs_public_ip]
}

output aks_client_certificate {
  value = azurerm_kubernetes_cluster.nxs_aks.kube_config.0.client_certificate
  depends_on = [azurerm_kubernetes_cluster_node_pool.nxs_aks_gpupool1, azurerm_public_ip.nxs_public_ip]
}

output aks_client_client_key {
  value = azurerm_kubernetes_cluster.nxs_aks.kube_config.0.client_key
  depends_on = [azurerm_kubernetes_cluster_node_pool.nxs_aks_gpupool1, azurerm_public_ip.nxs_public_ip]
}

output aks_client_cluster_ca_certificate {
  value = azurerm_kubernetes_cluster.nxs_aks.kube_config.0.cluster_ca_certificate
  depends_on = [azurerm_kubernetes_cluster_node_pool.nxs_aks_gpupool1, azurerm_public_ip.nxs_public_ip]
}

output aks_tenant_id {
  value = azurerm_kubernetes_cluster.nxs_aks.identity[0].tenant_id
  depends_on = [azurerm_kubernetes_cluster_node_pool.nxs_aks_gpupool1, azurerm_public_ip.nxs_public_ip]
}

output aks_kv_secrets_provider_client_id {
  #value = azurerm_kubernetes_cluster.nxs_aks.addon_profile[0].azure_keyvault_secrets_provider[0].secret_identity[0].client_id
  value = azurerm_kubernetes_cluster.nxs_aks.key_vault_secrets_provider[0].secret_identity[0].client_id
  depends_on = [azurerm_kubernetes_cluster_node_pool.nxs_aks_gpupool1, azurerm_public_ip.nxs_public_ip]
}

output aks_kv_secrets_provider_object_id {
  #value = azurerm_kubernetes_cluster.nxs_aks.addon_profile[0].azure_keyvault_secrets_provider[0].secret_identity[0].object_id
  value = azurerm_kubernetes_cluster.nxs_aks.key_vault_secrets_provider[0].secret_identity[0].object_id
  depends_on = [azurerm_kubernetes_cluster_node_pool.nxs_aks_gpupool1, azurerm_public_ip.nxs_public_ip]
}

output aks_public_ip {
  value = azurerm_public_ip.nxs_public_ip.ip_address
  depends_on = [azurerm_kubernetes_cluster_node_pool.nxs_aks_gpupool1, azurerm_public_ip.nxs_public_ip]
}

output aks_domain_name_label {
  value = azurerm_public_ip.nxs_public_ip.domain_name_label
  depends_on = [azurerm_kubernetes_cluster_node_pool.nxs_aks_gpupool1, azurerm_public_ip.nxs_public_ip]
}

output aks_domain_name_fqdn {
  value = azurerm_public_ip.nxs_public_ip.fqdn
  depends_on = [azurerm_kubernetes_cluster_node_pool.nxs_aks_gpupool1, azurerm_public_ip.nxs_public_ip]
}

output aks_kube_config {
  value = azurerm_kubernetes_cluster.nxsapp_aks.kube_config_raw
}