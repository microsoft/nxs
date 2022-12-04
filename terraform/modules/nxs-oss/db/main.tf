provider "azurerm" {
  features {}
  subscription_id = var.base.subscription_id
  tenant_id       = var.base.tenant_id
  alias           = "user_subscription"
}

# create mongodb

# create a random suffix for db
resource "random_password" "db_name_suffix" {
  length = 4
  special = false
  min_special = 0
  min_numeric = 4
  override_special = "-_?@#"
}

resource "azurerm_cosmosdb_account" "nxs_mongodb" {
  provider            = azurerm.user_subscription
  name                = lower(substr("nxs-${var.base.deployment_name}-db-${random_password.db_name_suffix.result}", 0, 24))
  location            = var.base.location
  resource_group_name = var.base.rg_name
  offer_type          = "Standard"
  kind                = "MongoDB"

  consistency_policy {
    consistency_level = "Eventual"
  }

  geo_location {
    location = var.base.location
    failover_priority = 0
  }

  capabilities {
    name = "EnableMongo"
  }
}

# create database for mongodb
resource "azurerm_cosmosdb_mongo_database" "nxs_mongodb_maindb" {
  name                = "NXS"
  resource_group_name = azurerm_cosmosdb_account.nxs_mongodb.resource_group_name
  account_name        = azurerm_cosmosdb_account.nxs_mongodb.name
  autoscale_settings {
    max_throughput = var.db_autoscale_max_throughput
  }
}

# create Models collection
resource "azurerm_cosmosdb_mongo_collection" "maindb_model_collection" {
  name                = "Models"
  resource_group_name = azurerm_cosmosdb_account.nxs_mongodb.resource_group_name
  account_name        = azurerm_cosmosdb_account.nxs_mongodb.name
  database_name       = azurerm_cosmosdb_mongo_database.nxs_mongodb_maindb.name

  default_ttl_seconds = "-1"
  shard_key           = "zone"
  #throughput          = 400

  index {
    keys   = ["_id"]
    unique = true
  }

  index {
    keys   = ["model_uuid", "zone"]
    unique = false
  }

  index {
    keys   = ["model_uuid"]
    unique = false
  }
}

# create Pipelines collection
resource "azurerm_cosmosdb_mongo_collection" "maindb_pipline_collection" {
  name                = "Pipelines"
  resource_group_name = azurerm_cosmosdb_account.nxs_mongodb.resource_group_name
  account_name        = azurerm_cosmosdb_account.nxs_mongodb.name
  database_name       = azurerm_cosmosdb_mongo_database.nxs_mongodb_maindb.name

  default_ttl_seconds = "-1"
  shard_key           = "zone"
  #throughput          = 400

  index {
    keys   = ["_id"]
    unique = true
  }

  index {
    keys   = ["pipeline_uuid", "zone"]
    unique = false
  }

  index {
    keys   = ["is_public", "zone"]
    unique = false
  }

  index {
    keys   = ["pipeline_uuid"]
    unique = false
  }

  index {
    keys   = ["is_public"]
    unique = false
  }
}

# create Stats collection
resource "azurerm_cosmosdb_mongo_collection" "maindb_stat_collection" {
  name                = "Stats"
  resource_group_name = azurerm_cosmosdb_account.nxs_mongodb.resource_group_name
  account_name        = azurerm_cosmosdb_account.nxs_mongodb.name
  database_name       = azurerm_cosmosdb_mongo_database.nxs_mongodb_maindb.name

  default_ttl_seconds = "-1"
  shard_key           = "zone"
  #throughput          = 400

  index {
    keys   = ["_id"]
    unique = true
  }

  index {
    keys   = ["utc_ts", "zone"]
    unique = false
  }

  index {
    keys   = ["utc_ts"]
    unique = false
  }
}

output db_info {
  value = {
    nxs_mongodb_key = azurerm_cosmosdb_account.nxs_mongodb.primary_key
    nxs_mongodb_endpoint = azurerm_cosmosdb_account.nxs_mongodb.endpoint
    nxs_mongodb_conn_str = azurerm_cosmosdb_account.nxs_mongodb.connection_strings[0]
    nxs_mongodb_maindb_name = azurerm_cosmosdb_mongo_database.nxs_mongodb_maindb.name
  }
}
