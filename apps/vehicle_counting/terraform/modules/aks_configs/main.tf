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

provider "helm" {
  kubernetes {
    host                   = var.aks_base.host
    username               = var.aks_base.username
    password               = var.aks_base.password
    client_certificate     = base64decode(var.aks_base.client_certificate)
    client_key             = base64decode(var.aks_base.client_key)
    cluster_ca_certificate = base64decode(var.aks_base.cluster_ca_certificate)
  }
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

# create vcapp namespace
resource "kubernetes_namespace" "app_ns" {
  metadata {
    name = var.app_namespace
  }
}

resource "kubectl_manifest" "secrets_provider" {
  wait = true
  yaml_body = <<YAML
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  namespace: "${var.app_namespace}"
  name: nxsapp-kv-sync
spec:
  provider: azure
  parameters:
    usePodIdentity: "false"         
    useVMManagedIdentity: "true"   
    userAssignedIdentityID: ${var.aks_base.secrets_provider_client_id}
    keyvaultName: ${var.kv_base.kv_name}
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
          objectName: NxsApiKey
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
        - |
          objectName: AksKubeConfig
          objectType: secret
          objectVersion: ""
        - |
          objectName: AppApiContainer
          objectType: secret
          objectVersion: ""
        - |
          objectName: AppWorkerContainer
          objectType: secret
          objectVersion: ""
        - |
          objectName: AppReportCountsInterval
          objectType: secret
          objectVersion: ""
        - |
          objectName: NxsDetectorUUID
          objectType: secret
          objectVersion: ""
        - |
          objectName: NxsTrackerUUID
          objectType: secret
          objectVersion: ""
    resourceGroup: "" #REQUIRED
    tenantId: ${var.aks_base.tenant_id}
  secretObjects:
    - data:
      - key: API_KEY
        objectName: ApiKey
      - key: NXS_URL
        objectName: NxsUrl
      - key: NXS_API_KEY
        objectName: NxsApiKey
      - key: MONGODB_CONNECTION_STR
        objectName: MongoDbConnectionStr
      - key: MONGODB_MAINDB_NAME
        objectName: MongoDbMaindbName
      - key: BLOBSTORE_CONNECTION_STR
        objectName: BlobstoreConnectionStr
      - key: BLOBSTORE_CONTAINER_NAME
        objectName: BlobstoreContainerName
      - key: APP_WORKER_CONTAINER
        objectName: AppWorkerContainer
      - key: APP_REPORT_COUNTS_INTERVAL
        objectName: AppReportCountsInterval
      - key: NXS_DETECTOR_UUID
        objectName: NxsDetectorUUID
      - key: NXS_TRACKER_UUID
        objectName: NxsTrackerUUID
      secretName: nxsappkv
      type: Opaque
  YAML
  depends_on = [
    kubernetes_namespace.app_ns
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
    value = "${var.aks_base.public_ip}"
  }
  set {
    name  = "controller.service.annotations\\.service.beta.kubernetes.io/azure-dns-label-name"
    value = "${var.aks_base.domain_name_label}"
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
    email: "${var.base.ssl_cert_owner_email}"
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
  yaml_body = templatefile("${path.module}/yaml/nxsapp_api_svc.yaml",
    {
      APP_NS: "${var.app_namespace}"
    }
  )
  depends_on = [
    kubernetes_namespace.app_ns
  ]
}

resource "kubectl_manifest" "nxsapp_ing_service" {
  wait = true
  yaml_body = templatefile("${path.module}/yaml/nxsapp_ing.yaml",
    {
      APP_NS: "${var.app_namespace}"
      DNS_FQDN: var.aks_base.domain_name_fqdn
    }
  )
  depends_on = [
    kubernetes_namespace.app_ns
  ]
}

resource "kubernetes_secret" "regcred" {  
  metadata {
    name = "regcred"
    namespace = "${var.app_namespace}"
  }

  data = {
    ".dockerconfigjson" = jsonencode({
      auths = {
        "${var.base.acr_login_server}" = {
          auth = "${base64encode("${var.base.acr_username}:${var.base.acr_password}")}"
        }
      }
    })
  }

  type = "kubernetes.io/dockerconfigjson"
  depends_on = [kubernetes_namespace.app_ns]
}