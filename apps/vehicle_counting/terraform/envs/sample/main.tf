# do not put special or uppercase characters in deployment_name
locals {
  deployment_name = "vc"                                    # change this to your deployment name
}

module "nxs" {
  source = "../../modules/root"  
  subscription_id       = ""                                  # user's subscription_id
  tenant_id             = ""                                  # user's tenant_id
  deployment_name       = local.deployment_name
  rg_name               = "nxsapp-${local.deployment_name}"
  location              = ""                                  # location to deploy (e.g., westus2)
  admin_group_object_id = ""                                  # admin group of this deployment
  ssl_cert_owner_email  = ""                                  # email to register for let's encrypt ssl certificate for secured connection between clients and nxs
  aks_cpu_node_vm_size  = "Standard_D2s_v4"
  aks_min_cpu_node_count = 2  # minimum number of cpu nodes, should be at least 3 for Standard_D2s_v4  
  aks_max_cpu_node_count = 6  # maximum number of cpu nodes, should be at least aks_min_cpu_node_count  
  acr_login_server      = ""              # change this to acr where you store nxs container
  acr_username          = ""
  acr_password          = ""
  api_domain_name_label = ""              # e.g., nxsapp-vehicle-count ; the url to access app would be nxsapp-vehicle-count.<location>>.cloudapp.azure.com
  nxs_url               = ""              # base url to access NXS cluster
  nxs_api_key           = ""              # api key to access NXS cluster 
  nxsapp_api_container  = ""              # path to api container e.g., ossnxs.azurecr.io/vcapi:v0.1.2
  nxsapp_worker_container = ""            # path to worker container e.g., ossnxs.azurecr.io/vcworker:v0.1
  data_retention_days   = 18              # data retention in days for debug data
  data_delete_snapshot_retention_days = 3 # snapshot retention in days after deleting debug data
}