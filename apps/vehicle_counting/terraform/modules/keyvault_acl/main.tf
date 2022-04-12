provider "azurerm" {
  features {}
  subscription_id = var.base.subscription_id
  tenant_id       = var.base.tenant_id
  alias           = "user_subscription"
}

resource "azurerm_key_vault_access_policy" "kv_aks_kv_secrets_provider_acl" {
  provider     = azurerm.user_subscription
  key_vault_id = var.kv_base.kv_id
  tenant_id    = var.aks_base.tenant_id
  object_id    = var.aks_base.secrets_provider_object_id

  secret_permissions = [
      "Get",
      "Set",
      "List"
    ]
}
