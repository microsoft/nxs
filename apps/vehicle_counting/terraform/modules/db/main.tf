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

resource "azurerm_cosmosdb_account" "nxsapp_mongodb" {
  provider            = azurerm.user_subscription
  name                = lower(substr("nxsapp-${var.base.deployment_name}-db-${random_password.db_name_suffix.result}", 0, 24))
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
resource "azurerm_cosmosdb_mongo_database" "nxsapp_mongodb_maindb" {
  name                = "VehicleCounting"
  resource_group_name = azurerm_cosmosdb_account.nxsapp_mongodb.resource_group_name
  account_name        = azurerm_cosmosdb_account.nxsapp_mongodb.name
  autoscale_settings {
    max_throughput = var.db_autoscale_max_throughput
  }
}

# create counts collection
resource "azurerm_cosmosdb_mongo_collection" "maindb_counts_collection" {
  name                = "counts"
  resource_group_name = azurerm_cosmosdb_account.nxsapp_mongodb.resource_group_name
  account_name        = azurerm_cosmosdb_account.nxsapp_mongodb.name
  database_name       = azurerm_cosmosdb_mongo_database.nxsapp_mongodb_maindb.name

  default_ttl_seconds = "${var.db_item_ttl}"
  shard_key           = "zone"
  #throughput          = 400

  index {
    keys   = ["_id"]
    unique = true
  }

  index {
    keys   = ["video_uuid", "zone"]
    unique = false
  }

  index {
    keys   = ["video_uuid", "timestamp", "zone"]
    unique = false
  }

  index {
    keys   = ["video_uuid"]
    unique = false
  }

  index {
    keys   = ["video_uuid", "timestamp"]
    unique = false
  }
}

# create logs collection
resource "azurerm_cosmosdb_mongo_collection" "maindb_logs_collection" {
  name                = "logs"
  resource_group_name = azurerm_cosmosdb_account.nxsapp_mongodb.resource_group_name
  account_name        = azurerm_cosmosdb_account.nxsapp_mongodb.name
  database_name       = azurerm_cosmosdb_mongo_database.nxsapp_mongodb_maindb.name

  default_ttl_seconds = "${var.db_item_ttl}"
  shard_key           = "zone"
  #throughput          = 400

  index {
    keys   = ["_id"]
    unique = true
  }

  index {
    keys   = ["video_uuid", "zone"]
    unique = false
  }

  index {
    keys   = ["video_uuid", "start_ts", "zone"]
    unique = false
  }

  index {
    keys   = ["video_uuid"]
    unique = false
  }

  index {
    keys   = ["video_uuid", "start_ts"]
    unique = false
  }

}

# create tasks collection
resource "azurerm_cosmosdb_mongo_collection" "maindb_tasks_collection" {
  name                = "tasks"
  resource_group_name = azurerm_cosmosdb_account.nxsapp_mongodb.resource_group_name
  account_name        = azurerm_cosmosdb_account.nxsapp_mongodb.name
  database_name       = azurerm_cosmosdb_mongo_database.nxsapp_mongodb_maindb.name

  # tasks info should be in db in case app runs longer than ttl
  default_ttl_seconds = "-1"
  shard_key           = "zone"
  #throughput          = 400

  index {
    keys   = ["_id"]
    unique = true
  }

  index {
    keys   = ["video_uuid", "zone"]
    unique = false
  }

  index {
    keys   = ["video_uuid"]
    unique = false
  }
}

output db_base {
  value = {
    db_name = azurerm_cosmosdb_mongo_database.nxsapp_mongodb_maindb.name
    db_key = azurerm_cosmosdb_account.nxsapp_mongodb.primary_key
    db_endpoint = azurerm_cosmosdb_account.nxsapp_mongodb.endpoint
    db_conn_str = azurerm_cosmosdb_account.nxsapp_mongodb.connection_strings[0]    
  }
}