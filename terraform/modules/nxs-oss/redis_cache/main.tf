provider "azurerm" {
  features {}
  subscription_id = var.base.subscription_id
  tenant_id       = var.base.tenant_id
  alias           = "user_subscription"
}

# create a random suffix for redis
resource "random_password" "redis_name_suffix" {
  length = 4
  special = false
  min_special = 0
  min_numeric = 4
  override_special = "-_?@#"
}

resource "azurerm_redis_cache" "nxs_redis" {
  provider            = azurerm.user_subscription
  name                = lower(substr("nxs-${var.base.deployment_name}-redis-${random_password.redis_name_suffix.result}", 0, 24))
  location            = var.base.location
  resource_group_name = var.base.rg_name
  capacity            = var.az_redis_cache_capacity
  family              = var.az_redis_cache_family_type
  sku_name            = var.az_redis_cache_sku
  enable_non_ssl_port = false
  minimum_tls_version = "1.2"

  redis_version = 6

  redis_configuration {
  }
}

output redis_address {
  value = azurerm_redis_cache.nxs_redis.hostname
}

output redis_port {
  value = azurerm_redis_cache.nxs_redis.ssl_port
}

output redis_password {
  value = azurerm_redis_cache.nxs_redis.primary_access_key
}

output redis_use_ssl {
    value = "true"
}