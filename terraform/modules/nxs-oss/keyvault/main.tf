provider "azurerm" {
  features {}
  subscription_id = var.base.subscription_id
  tenant_id       = var.base.tenant_id
  alias           = "user_subscription"
}

# create a random suffix for keyvault
resource "random_password" "kv_name_suffix" {
  length = 4
  special = false
  min_special = 0
  min_numeric = 4
  override_special = "-_?@#"
}

resource "azurerm_key_vault" "nxs_kv" {
  provider            = azurerm.user_subscription
  name                = lower(substr("nxs-${var.base.deployment_name}-kv-${random_password.kv_name_suffix.result}", 0, 24))
  location            = var.base.location
  resource_group_name = var.base.rg_name
  tenant_id           = var.base.tenant_id

  soft_delete_retention_days  = 7
  sku_name = "premium"

  # give access to the current user (running the TF script) so we can populate the KV with secrets
  access_policy {
    tenant_id = var.base.tenant_id
    object_id = var.base.admin_group_object_id

    secret_permissions = [
      "Get",
      "Set",
      "Delete",
      "List",
      "Recover",
      "Purge",
      "Recover"
    ]
  }

  lifecycle {
    ignore_changes = [
      access_policy
    ]
  }
}

output kv_id {
    value = azurerm_key_vault.nxs_kv.id
}

output kv_uri {
    value = azurerm_key_vault.nxs_kv.vault_uri
}

output kv_name {
    value = azurerm_key_vault.nxs_kv.name
}