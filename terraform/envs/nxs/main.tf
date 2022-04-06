# do not put special or uppercase characters in deployment_name
locals {
  deployment_name = "demo"                                    # change this to your deployment name
}

module "nxs" {
  source = "../../modules/nxs-oss/root"  
  subscription_id       = ""                                  # user's subscription_id
  tenant_id             = ""                                  # user's tenant_id
  deployment_name       = local.deployment_name
  rg_name               = "nxs-${local.deployment_name}"
  location              = ""                                  # location to deploy
  admin_group_object_id = ""                                  # admin group of this deployment
  ssl_cert_owner_email  = ""                                  # email to register for let's encrypt ssl certificate for secured connection between clients and nxs
  aks_cpu_node_vm_size  = "Standard_D2s_v4"
  aks_gpu_node_vm_size  = "Standard_NC4as_T4_v3"
  acr_login_server      = "nxsacrxxx.azurecr.io"              # change this to acr where you store nxs container
  acr_username          = ""
  acr_password          = ""
}

output nxs_url {
  value = module.nxs.nxs_url
}

output nxs_api_key {
  value = module.nxs.nxs_api_key
  sensitive = true
}