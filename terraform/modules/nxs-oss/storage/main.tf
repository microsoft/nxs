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
  name                     = substr(replace("nxs${var.base.deployment_name}storage${random_password.storage_name_suffix.result}", "-", ""), 0, 24)
  resource_group_name      = var.base.rg_name
  location                 = var.base.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_container" "nxs" {
  name                  = "nxs"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"
}

output storage_info {
  value = {
    nxs_storage_connection_string = azurerm_storage_account.main.primary_blob_connection_string
    nxs_storage_container_name = azurerm_storage_container.nxs.name
  }
}