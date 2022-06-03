# do not put special or uppercase characters in deployment_name
locals {
    # shared configurations
    base = {
        deployment_name         = "oss"                                 # change this to your deployment name
        subscription_id         = ""                                    # user's subscription_id
        tenant_id               = ""                                    # user's tenant_id
        location                = ""                                    # location to deploy (e.g., westus2)
        admin_group_object_id   = ""                                    # admin group of this deployment
        ssl_cert_owner_email    = ""                                    # email to register for let's encrypt ssl certificate
    }
    
    # nxs configurations
    nxs_config = {
        # aks configs
        aks = {
            aks_cpu_node_vm_size = "standard_d2s_v3"
            aks_min_cpu_node_count = 3
            aks_max_cpu_node_count = 6
            aks_gpu_node_vm_size  = "Standard_NC4as_T4_v3"
            aks_min_gpu_node_count = 0
            aks_max_gpu_node_count = 2
        }    

        # container register configs - change this to acr where you store nxs container
        acr = {
            acr_login_server      = ""
            acr_username          = ""
            acr_password          = ""
        }

        # container configs
        containers = {
            scheduler = {
                nxs_scheduler_image             = "nxsacrxxx.azurecr.io/nxs/dev"
                nxs_scheduler_image_tag         = "v0.1.0"
            }
            workload_manager = {
                nxs_workload_manager_image      = "nxsacrxxx.azurecr.io/nxs/dev"
                nxs_workload_manager_image_tag  = "v0.1.0"
            }
            backend_monitor = {
                nxs_backend_monitor_image       = "nxsacrxxx.azurecr.io/nxs/dev"
                nxs_backend_monitor_image_tag   = "v0.1.0"
            }
            backend_gpu = {
                nxs_backend_gpu_image           = "nxsacrxxx.azurecr.io/nxs/dev"
                nxs_backend_gpu_image_tag       = "v0.1.0"
            }
            frontend = {
                nxs_api_image                   = "nxsacrxxx.azurecr.io/nxs/dev"
                nxs_api_image_tag               = "v0.1.0"
                min_num_frontend_replicas       = 2
                max_num_frontend_replicas       = 8
                enable_api_v1                   = false
            }
            model_initializer = {
                nxs_initializer_image           = "nxsacrxxx.azurecr.io/nxs/dev"
                nxs_initializer_image_tag       = "v0.1.0"
                run_initializer                 = false
            }
        }

        # redis configs
        redis = {
            use_azure_redis_cache = true

            azure_redis_cache = {
                # applicable when use_azure_redis_cache is true
                azure_redis_cache_sku               = "Standard"
                azure_redis_cache_family_type       = "C"
                azure_redis_cache_capacity          = 2
            }
        }

        # [OPTIONAL CONFIGS]
        # db configs
        db = {
            db_autoscale_max_throughput             = 4000
        }
    }
}

module "nxs" {
    source = "../../modules/nxs-oss/root"  
    base = local.base
    nxs_config = local.nxs_config
}