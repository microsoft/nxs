terraform {
  required_providers {
    kubectl = {
      source  = "gavinbunney/kubectl"
      version = ">= 1.13"
    }
  }
}

provider "kubernetes" {
  host                   = var.aks_base.host
  username               = var.aks_base.username
  password               = var.aks_base.password
  client_certificate     = base64decode(var.aks_base.client_certificate)
  client_key             = base64decode(var.aks_base.client_key)
  cluster_ca_certificate = base64decode(var.aks_base.cluster_ca_certificate)
}

provider "kubectl" {
  host                   = var.aks_base.host
  username               = var.aks_base.username
  password               = var.aks_base.password
  client_certificate     = base64decode(var.aks_base.client_certificate)
  client_key             = base64decode(var.aks_base.client_key)
  cluster_ca_certificate = base64decode(var.aks_base.cluster_ca_certificate)
  load_config_file       = false
}

resource "kubectl_manifest" "nxsapp_api" {
  wait = true
  wait_for_rollout = true
  yaml_body = templatefile("${path.module}/yaml/nxsapp_api.yaml",
    {
      API_CONTAINER: var.base.nxsapp_api_container
    }
  )
  timeouts {
    create = "30m"
  }
  depends_on = [var.aks_configs_completed, var.kv_store_secrets_completed]  
}