terraform {
  required_providers {
    kubectl = {
      source  = "gavinbunney/kubectl"
      version = ">= 1.13"
    }
  }
}

provider "kubernetes" {
  host                   = var.aks_host
  username               = var.aks_username
  password               = var.aks_password
  client_certificate     = base64decode(var.aks_client_certificate)
  client_key             = base64decode(var.aks_client_client_key)
  cluster_ca_certificate = base64decode(var.aks_client_cluster_ca_certificate)
}

provider "kubectl" {
  host                   = var.aks_host
  username               = var.aks_username
  password               = var.aks_password
  client_certificate     = base64decode(var.aks_client_certificate)
  client_key             = base64decode(var.aks_client_client_key)
  cluster_ca_certificate = base64decode(var.aks_client_cluster_ca_certificate)
  load_config_file       = false
}

# create vcapp namespace
resource "kubernetes_namespace" "app_ns" {
  metadata {
    name = "vcapp"
  }
}

resource "kubectl_manifest" "secrets_provider" {
  wait = true
  yaml_body = <<YAML
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  namespace: vcapp
  name: nxs-vcapp-kv-sync
spec:
  provider: azure
  parameters:
    usePodIdentity: "false"         
    useVMManagedIdentity: "true"   
    userAssignedIdentityID: ${var.aks_kv_secrets_provider_client_id}
    keyvaultName: ${var.kv_name}
    cloudName: ""          
    cloudEnvFileName: ""   
    objects:  |
      array:
        - |
          objectName: ApiKey
          objectType: secret
          objectVersion: ""
        - |
          objectName: NxsUrl
          objectType: secret
          objectVersion: ""
        - |
          objectName: MongoDbConnectionStr
          objectType: secret
          objectVersion: ""
        - |
          objectName: MongoDbMaindbName
          objectType: secret
          objectVersion: ""
        - |
          objectName: BlobstoreConnectionStr
          objectType: secret
          objectVersion: ""
        - |
          objectName: BlobstoreContainerName
          objectType: secret
          objectVersion: ""
    resourceGroup: "" #REQUIRED
    tenantId: ${var.aks_tenant_id}
  secretObjects:
    - data:
      - key: API_KEY
        objectName: ApiKey
      - key: NXS_URL
        objectName: NxsUrl
      - key: MONGODB_CONNECTION_STR
        objectName: MongoDbConnectionStr
      - key: MONGODB_MAINDB_NAME
        objectName: MongoDbMaindbName
      - key: BLOBSTORE_CONNECTION_STR
        objectName: BlobstoreConnectionStr
      - key: BLOBSTORE_CONTAINER_NAME
        objectName: BlobstoreContainerName
      secretName: nxsvckv
      type: Opaque
  YAML
  depends_on = [
    kubernetes_namespace.vcapp_ns
  ]
}

# assign public ip to aks ingress
resource "kubernetes_namespace" "ingress_basic" {
  metadata {
    name = "ingress-basic"
    labels = {
      "cert-manager.io/disable-validation" = true
    }
  }
}

resource "helm_release" "nginx_ingress" {
  name       = "nginx-ingress"
  repository = "https://kubernetes.github.io/ingress-nginx"
  chart      = "ingress-nginx"
  namespace  = "ingress-basic"
  version    = "4.0.13"

  set {
    name  = "controller.replicaCount"
    value = 2
  }
  set {
    name  = "controller.nodeSelector\\.kubernetes.io/os"
    value = "linux"
  }
  set {
    name  = "controller.image.registry"
    value = "k8s.gcr.io"
  }
  set {
    name  = "controller.image.image"
    value = "ingress-nginx/controller"
  }
  set {
    name  = "controller.image.tag"
    value = "v1.0.4"
  }
  set {
    name  = "controller.image.digest"
    value = ""
  }

  set {
    name  = "controller.admissionWebhooks.patch.nodeSelector\\.kubernetes.io/os"
    value = "linux"
  }
  set {
    name  = "controller.admissionWebhooks.patch.image.registry"
    value = "k8s.gcr.io"
  }
  set {
    name  = "controller.admissionWebhooks.patch.image.image"
    value = "ingress-nginx/kube-webhook-certgen"
  }
  set {
    name  = "controller.admissionWebhooks.patch.image.tag"
    value = "v1.1.1"
  }
  set {
    name  = "controller.admissionWebhooks.patch.image.digest"
    value = ""
  }

  set {
    name  = "defaultBackend.nodeSelector\\.kubernetes.io/os"
    value = "linux"
  }
  set {
    name  = "defaultBackend.image.registry"
    value = "k8s.gcr.io"
  }
  set {
    name  = "defaultBackend.image.image"
    value = "defaultbackend-amd64"
  }
  set {
    name  = "defaultBackend.image.tag"
    value = "1.5"
  }
  set {
    name  = "defaultBackend.image.digest"
    value = ""
  }
  set {
    name  = "controller.service.loadBalancerIP"
    value = "${var.aks_public_ip_address}"
  }
  set {
    name  = "controller.service.annotations\\.service.beta.kubernetes.io/azure-dns-label-name"
    value = "${var.aks_domain_name_label}"
  }  
  depends_on = [
    kubernetes_namespace.ingress_basic
  ]
}

# Install cert-manager
resource "helm_release" "cert_manager" {
  name       = "cert-manager"
  repository = "https://charts.jetstack.io"
  chart      = "cert-manager"
  namespace = "ingress-basic"
  version    = "v1.5.4"

  set {
    name  = "installCRDs"
    value = true
  }
  set {
    name  = "controller.nodeSelector\\.beta.kubernetes.io/os"
    value = "linux"
  }
  set {
    name  = "image.repository"
    value = "quay.io/jetstack/cert-manager-controller"
  }
  set {
    name  = "image.tag"
    value = "v1.5.4"
  }
  set {
    name  = "webhook.image.repository"
    value = "quay.io/jetstack/cert-manager-webhook"
  }
  set {
    name  = "webhook.image.tag"
    value = "v1.5.4"
  }
  set {
    name  = "cainjector.image.repository"
    value = "quay.io/jetstack/cert-manager-cainjector"
  }
  set {
    name  = "cainjector.image.tag"
    value = "v1.5.4"
  }
  depends_on = [
    helm_release.nginx_ingress
  ]
}

resource "kubectl_manifest" "ca_issuer" {
  wait = true
  yaml_body = <<YAML
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: "${var.ssl_cert_owner_email}"
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
          podTemplate:
            spec:
              nodeSelector:
                "kubernetes.io/os": linux
  YAML
  depends_on = [
    helm_release.cert_manager
  ]
}

# create api-service and ing-service
resource "kubectl_manifest" "nxsapp_api_service" {
  wait = true
  yaml_body = file("${path.module}/yaml/nxsapp_api_svc.yaml")
  depends_on = [
    kubernetes_namespace.vcapp_ns
  ]
}

resource "kubectl_manifest" "nxsapp_ing_service" {
  wait = true
  yaml_body = templatefile("${path.module}/yaml/nxsapp_api_svc.yaml",
    {
      DNS_FQDN: var.aks_domain_name_fqdn
    }
  )
  depends_on = [
    kubernetes_namespace.vcapp_ns
  ]
}

resource "kubernetes_secret" "regcred" {  
  metadata {
    name = "regcred"
    namespace = "nxs"
  }

  data = {
    ".dockerconfigjson" = jsonencode({
      auths = {
        #"${data.azurerm_container_registry.watchfor_acr.login_server}" = {
        #  auth = "${base64encode("${data.azurerm_container_registry.watchfor_acr.admin_username}:${data.azurerm_container_registry.watchfor_acr.admin_password}")}"
        #}
        "${var.acr_login_server}" = {
          auth = "${base64encode("${var.acr_user_name}:${var.acr_password}")}"
        }
      }
    })
  }

  type = "kubernetes.io/dockerconfigjson"
  depends_on = [kubernetes_namespace.vcapp_ns]
}