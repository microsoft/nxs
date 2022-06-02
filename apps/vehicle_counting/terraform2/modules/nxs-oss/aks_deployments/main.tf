terraform {
  required_providers {
    kubectl = {
      source  = "gavinbunney/kubectl"
      version = ">= 1.13"
    }
  }
}

provider "kubernetes" {
  host                   = var.aks_info.aks_host
  username               = var.aks_info.aks_username
  password               = var.aks_info.aks_password
  client_certificate     = base64decode(var.aks_info.aks_client_certificate)
  client_key             = base64decode(var.aks_info.aks_client_client_key)
  cluster_ca_certificate = base64decode(var.aks_info.aks_client_cluster_ca_certificate)
}

provider "helm" {
  kubernetes {
    host                   = var.aks_info.aks_host
    username               = var.aks_info.aks_username
    password               = var.aks_info.aks_password
    client_certificate     = base64decode(var.aks_info.aks_client_certificate)
    client_key             = base64decode(var.aks_info.aks_client_client_key)
    cluster_ca_certificate = base64decode(var.aks_info.aks_client_cluster_ca_certificate)
  }
}

provider "kubectl" {
  host                   = var.aks_info.aks_host
  username               = var.aks_info.aks_username
  password               = var.aks_info.aks_password
  client_certificate     = base64decode(var.aks_info.aks_client_certificate)
  client_key             = base64decode(var.aks_info.aks_client_client_key)
  cluster_ca_certificate = base64decode(var.aks_info.aks_client_cluster_ca_certificate)
  load_config_file       = false
}

resource "kubectl_manifest" "nxs_scheduler" {
  wait = true
  wait_for_rollout = true
  #yaml_body = file("${path.module}/yaml/nxs_scheduler.yaml")
  yaml_body = templatefile("${path.module}/yaml/nxs_scheduler.yaml",
    {
      IMAGE: var.nxs_scheduler_image
      IMAGE_TAG: var.nxs_scheduler_image_tag
      CPU_REQUEST: var.nxs_scheduler_cpu_requests
      MEMORY_REQUEST: var.nxs_scheduler_memory_requests
    }
  )
  timeouts {
    create = "30m"
  }
  depends_on = [var.aks_configs_info]  
}

resource "kubectl_manifest" "nxs_workload_manager" {
  wait = true
  wait_for_rollout = true
  #yaml_body = file("${path.module}/yaml/nxs_workload_manager.yaml")
  yaml_body = templatefile("${path.module}/yaml/nxs_workload_manager.yaml",
    {
      IMAGE: var.nxs_workload_manager_image
      IMAGE_TAG: var.nxs_workload_manager_image_tag
      CPU_REQUEST: var.nxs_workload_manager_cpu_requests
      MEMORY_REQUEST: var.nxs_workload_manager_memory_requests
    }
  )
  timeouts {
    create = "30m"
  }
  depends_on = [
    kubectl_manifest.nxs_scheduler
  ]
}

resource "kubectl_manifest" "nxs_backend_monitor" {
  wait = true
  wait_for_rollout = true
  #yaml_body = file("${path.module}/yaml/nxs_backend_monitor.yaml")
  yaml_body = templatefile("${path.module}/yaml/nxs_backend_monitor.yaml",
    {
      IMAGE: var.nxs_backend_monitor_image
      IMAGE_TAG: var.nxs_backend_monitor_image_tag
      CPU_REQUEST: var.nxs_backend_monitor_cpu_requests
      MEMORY_REQUEST: var.nxs_backend_monitor_memory_requests
    }
  )
  timeouts {
    create = "30m"
  }
  depends_on = [
    kubectl_manifest.nxs_scheduler
  ]
}

resource "kubectl_manifest" "nxs_gpu_backends" {
  wait = true
  wait_for_rollout = true
  timeouts {
    create = "30m"
  }
  #yaml_body = file("${path.module}/yaml/nxs_backend_gpu.yaml")
  yaml_body = templatefile("${path.module}/yaml/nxs_backend_gpu.yaml",
    {
      NUM_REPLICAS: var.nxs_backend_gpu_num_replicas
      IMAGE: var.nxs_backend_gpu_image
      IMAGE_TAG: var.nxs_backend_gpu_image_tag
      CPU_REQUEST: var.nxs_backend_gpu_cpu_requests
      MEMORY_REQUEST: var.nxs_backend_gpu_memory_requests
    }
  )
  depends_on = [
    kubectl_manifest.nxs_scheduler
  ]
}

resource "kubectl_manifest" "nxs_api_servers" {
  wait = true
  wait_for_rollout = true
  #yaml_body = file("${path.module}/yaml/nxs_api.yaml")
  yaml_body = templatefile("${path.module}/yaml/nxs_api.yaml",
    {
      NUM_REPLICAS: var.nxs_api_min_num_replicas
      IMAGE: var.nxs_api_image
      IMAGE_TAG: var.nxs_api_image_tag
      CPU_REQUEST: var.nxs_api_cpu_requests
      MEMORY_REQUEST: var.nxs_api_memory_requests
      ENABLE_API_V1: tostring(var.enable_api_v1)
    }
  )
  timeouts {
    create = "30m"
  }
  depends_on = [
    kubectl_manifest.nxs_gpu_backends
  ]
}

resource "kubectl_manifest" "nxs_api_servers_hpa" {
  wait = true
  wait_for_rollout = true
  yaml_body = templatefile("${path.module}/yaml/nxs_api_hpa.yaml",
    {
      MAX_REPLICAS: var.nxs_api_max_num_replicas      
    }
  )
  timeouts {
    create = "30m"
  }
  depends_on = [
    kubectl_manifest.nxs_api_servers
  ]
}

resource "kubectl_manifest" "nxs_initializer" {
  count = var.run_initializer ? 1 : 0
  wait = true
  wait_for_rollout = true
  timeouts {
    create = "30m"
  }
  yaml_body = templatefile("${path.module}/yaml/nxs_initializer.yaml",
    {
      IMAGE: var.nxs_initializer_image
      IMAGE_TAG: var.nxs_initializer_image_tag      
    }
  )
  depends_on = [
    kubectl_manifest.nxs_api_servers
  ]
}