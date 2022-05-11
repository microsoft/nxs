provider "azurerm" {
  features {}
  subscription_id = var.base.subscription_id
  tenant_id       = var.base.tenant_id
  alias           = "user_subscription"
}

# create a random suffix for keyvault
resource "random_password" "storage_name_suffix" {
  length = 4
  special = false
  min_special = 0
  min_numeric = 4
  override_special = "-_?@#"
}

resource "azurerm_storage_account" "main" {
  provider            = azurerm.user_subscription
  name                     = substr(replace("nxsapp${var.base.deployment_name}storage${random_password.storage_name_suffix.result}", "-", ""), 0, 24)
  resource_group_name      = var.base.rg_name
  location                 = var.base.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_container" "nxsapp" {
  name                  = "nxsapp"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"
}

resource "azurerm_storage_management_policy" "delete_policy" {
  storage_account_id = azurerm_storage_account.main.id

  rule {
    name    = "rule1"
    enabled = true
    filters {
      prefix_match = ["nxsapp/logs"]
      blob_types   = ["blockBlob"]
    }
    actions {
      base_blob {
        delete_after_days_since_modification_greater_than          = var.data_retention_days
      }
      snapshot {
        delete_after_days_since_creation_greater_than = var.delete_snapshot_retention_days
      }
    }
  }
}

output storage_base {
  value = {
    connection_string = azurerm_storage_account.main.primary_blob_connection_string
    container_name = azurerm_storage_container.nxsapp.name
  }
}