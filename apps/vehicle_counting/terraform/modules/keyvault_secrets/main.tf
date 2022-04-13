provider "azurerm" {
  features {}
  subscription_id = var.base.subscription_id
  tenant_id       = var.base.tenant_id
  alias           = "user_subscription"
}

resource "azurerm_key_vault_secret" "secret" {
  provider     = azurerm.user_subscription
  for_each = var.secrets
  key_vault_id = var.keyvault_id
  name         = each.key
  value        = each.value
}

output kv_store_secrets_completed {
  value = true
  depends_on = [azurerm_key_vault_secret.secret]
}