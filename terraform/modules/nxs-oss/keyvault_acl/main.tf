provider "azurerm" {
  features {}
  subscription_id = var.base.subscription_id
  tenant_id       = var.base.tenant_id
  alias           = "user_subscription"
}

# grant current user to add secrets into kv
#resource "azurerm_key_vault_access_policy" "kv_user_acl" {
#  provider     = azurerm.user_subscription
#  key_vault_id = var.keyvault_id
#  tenant_id    = var.current_tenant_id
#  object_id    = var.current_object_id
#
#  secret_permissions = [
#      "Get",
#      "Set",
#      "List"
#    ]
#}

resource "azurerm_key_vault_access_policy" "kv_aks_kv_secrets_provider_acl" {
  provider     = azurerm.user_subscription
  key_vault_id = var.keyvault_id
  tenant_id    = var.aks_tenant_id
  object_id    = var.aks_kv_secrets_provider_object_id

  secret_permissions = [
      "Get",
      "Set",
      "List"
    ]
}

#resource "azurerm_key_vault_access_policy" "kv_aks_acl" {
#  key_vault_id = var.keyvault_id
#  tenant_id    = var.aks_tenant_id
#  object_id    = var.aks_principal_id
#
#  secret_permissions = [
#      "Get",
#      "Set",
#      "List"
#    ]
#}

#resource "azurerm_key_vault_access_policy" "kv_aks_kubelet_acl" {
#  key_vault_id = var.keyvault_id
#  tenant_id    = var.aks_tenant_id
#  object_id    = var.aks_kubelet_object_id
#
#  secret_permissions = [
#      "Get",
#      "Set",
#      "List"
#    ]
#}

