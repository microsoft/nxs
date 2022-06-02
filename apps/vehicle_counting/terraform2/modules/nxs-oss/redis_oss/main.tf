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

provider "kubectl" {
  host                   = var.aks_info.aks_host
  username               = var.aks_info.aks_username
  password               = var.aks_info.aks_password
  client_certificate     = base64decode(var.aks_info.aks_client_certificate)
  client_key             = base64decode(var.aks_info.aks_client_client_key)
  cluster_ca_certificate = base64decode(var.aks_info.aks_client_cluster_ca_certificate)
  load_config_file       = false
}

# create redis-operator namespace
resource "kubernetes_namespace" "redis_operator_ns" {
  count = var.create_module ? 1 : 0
  metadata {
    name = "redis-operator"
    labels = {
      "control-plane" = "redis-operator"
    }
  }
}

# create ot-operators namespace
resource "kubernetes_namespace" "ot_operator_ns" {
  count = var.create_module ? 1 : 0
  metadata {
    name = "ot-operators"
  }
}

resource "kubectl_manifest" "redis_step1" {
  count = var.create_module ? 1 : 0
  wait = true
  wait_for_rollout = true
  yaml_body = file("${path.module}/yaml/redis.redis.opstreelabs.in_redis.yaml")
  timeouts {
    create = "2m"
  }
  depends_on = [kubernetes_namespace.redis_operator_ns]  
}

resource "kubectl_manifest" "redis_step2" {
  count = var.create_module ? 1 : 0
  wait = true
  wait_for_rollout = true
  yaml_body = file("${path.module}/yaml/redis.redis.opstreelabs.in_redisclusters.yaml")
  timeouts {
    create = "2m"
  }
  depends_on = [kubectl_manifest.redis_step1]
}

resource "kubectl_manifest" "redis_step3" {
  count = var.create_module ? 1 : 0
  wait = true
  wait_for_rollout = true
  yaml_body = file("${path.module}/yaml/serviceaccount.yaml")
  timeouts {
    create = "2m"
  }
  depends_on = [kubectl_manifest.redis_step2]  
}

resource "kubectl_manifest" "redis_step4" {
  count = var.create_module ? 1 : 0
  wait = true
  wait_for_rollout = true
  yaml_body = file("${path.module}/yaml/role.yaml")
  timeouts {
    create = "2m"
  }
  depends_on = [kubectl_manifest.redis_step3]  
}

resource "kubectl_manifest" "redis_step5" {
  count = var.create_module ? 1 : 0
  wait = true
  wait_for_rollout = true
  yaml_body = file("${path.module}/yaml/role_binding.yaml")
  timeouts {
    create = "2m"
  }
  depends_on = [kubectl_manifest.redis_step4]  
}

resource "kubectl_manifest" "redis_step6" {
  count = var.create_module ? 1 : 0
  wait = true
  wait_for_rollout = true
  yaml_body = file("${path.module}/yaml/manager.yaml")
  timeouts {
    create = "2m"
  }
  depends_on = [kubectl_manifest.redis_step5]  
}

resource "random_password" "redis_password" {
  length = 16
  special = false
  min_special = 0
  min_numeric = 8
  override_special = "-_?@#"
}

resource "kubectl_manifest" "redis_conf" {
  count = var.create_module ? 1 : 0
  wait = true
  wait_for_rollout = true
  yaml_body = templatefile("${path.module}/yaml/redis_conf.yaml",
    {
      REDIS_PASSWORD: random_password.redis_password.result
    }
  )
  timeouts {
    create = "2m"
  }
  depends_on = [kubernetes_namespace.ot_operator_ns, kubectl_manifest.redis_step6]
}

resource "kubectl_manifest" "redis_server" {
  count = var.create_module ? 1 : 0
  wait = true
  wait_for_rollout = true
  yaml_body = templatefile("${path.module}/yaml/redis_standalone.yaml",
    {
      CPU_REQUEST: var.redis_cpu_per_node
      MEMORY_REQUEST: var.redis_memory_per_node
    }
  )
  timeouts {
    create = "10m"
  }
  depends_on = [kubectl_manifest.redis_conf]  
}

output redis_info {
  value = {
    redis_address = var.create_module ? "redis-standalone.ot-operators" : ""
    redis_port = 6379
    redis_password = var.create_module ? random_password.redis_password.result : ""
    redis_use_ssl = "false"
  }
  depends_on = [kubectl_manifest.redis_server]
}