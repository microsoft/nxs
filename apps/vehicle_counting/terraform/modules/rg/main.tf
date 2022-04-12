provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
  tenant_id       = var.tenant_id
  alias           = "user_subscription"
}

# resource group
resource "azurerm_resource_group" "rg" {
  provider = azurerm.user_subscription
  name     = lower(var.name)
  location = var.location
}
  
# assign the admin group as Owner of the resource group
resource "azurerm_role_assignment" "rg_to_group" {
  scope                = azurerm_resource_group.rg.id
  role_definition_name = "Contributor"
  principal_id         = var.admin_group_object_id

  depends_on = [
    azurerm_resource_group.rg
  ]
}

output "name" {
  value = azurerm_resource_group.rg.name
}