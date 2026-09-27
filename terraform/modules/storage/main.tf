# ADLS Gen2 storage account with medallion-architecture containers.

resource "random_string" "suffix" {
  length  = 5
  special = false
  upper   = false
}

resource "azurerm_storage_account" "adls" {
  name                     = substr(replace("st${var.name_prefix}${random_string.suffix.result}", "-", ""), 0, 24)
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = var.replication_type
  account_kind             = "StorageV2"
  is_hns_enabled           = true # enables ADLS Gen2 hierarchical namespace

  min_tls_version           = "TLS1_2"
  allow_nested_items_to_be_public = false

  network_rules {
    default_action             = "Deny"
    ip_rules                   = var.allowed_ip_ranges
    virtual_network_subnet_ids = [var.subnet_id_for_vnet_rule]
    bypass                     = ["AzureServices"]
  }

  blob_properties {
    versioning_enabled = true
    delete_retention_policy {
      days = 30
    }
  }

  tags = var.tags
}

resource "azurerm_storage_data_lake_gen2_filesystem" "raw" {
  name               = "raw"
  storage_account_id = azurerm_storage_account.adls.id
}

resource "azurerm_storage_data_lake_gen2_filesystem" "curated" {
  name               = "curated"
  storage_account_id = azurerm_storage_account.adls.id
}

resource "azurerm_storage_data_lake_gen2_filesystem" "checkpoints" {
  name               = "checkpoints"
  storage_account_id = azurerm_storage_account.adls.id
}

# Medallion sub-directories inside the curated filesystem
resource "azurerm_storage_data_lake_gen2_path" "silver" {
  path               = "silver"
  filesystem_name    = azurerm_storage_data_lake_gen2_filesystem.curated.name
  storage_account_id = azurerm_storage_account.adls.id
  resource           = "directory"
}

resource "azurerm_storage_data_lake_gen2_path" "gold" {
  path               = "gold"
  filesystem_name    = azurerm_storage_data_lake_gen2_filesystem.curated.name
  storage_account_id = azurerm_storage_account.adls.id
  resource           = "directory"
}

# Lifecycle management: the raw/ zone is immutable and append-only (see architecture.md),
# so it ages predictably and is a good candidate for tiering down from Hot instead of paying
# Hot-tier rates indefinitely for data that's rarely read after the initial Bronze ingestion
# window. Structured Streaming checkpoints under checkpoints/ are transient operational state
# with no business retention requirement, unlike raw/curated financial data, so they're deleted
# outright once stale. curated/ (Silver + Gold) is intentionally left out of this policy since
# it's actively queried by Databricks jobs, Snowflake external tables, and ad-hoc analysis.
resource "azurerm_storage_management_policy" "adls" {
  storage_account_id = azurerm_storage_account.adls.id

  rule {
    name    = "raw-zone-tiering"
    enabled = true

    filters {
      prefix_match = ["raw/"]
      blob_types   = ["blockBlob"]
    }

    actions {
      base_blob {
        tier_to_cool_after_days_since_modification_greater_than    = var.raw_zone_cool_tier_after_days
        tier_to_archive_after_days_since_modification_greater_than = var.raw_zone_archive_after_days
      }
    }
  }

  rule {
    name    = "checkpoints-cleanup"
    enabled = true

    filters {
      prefix_match = ["checkpoints/"]
      blob_types   = ["blockBlob"]
    }

    actions {
      base_blob {
        delete_after_days_since_modification_greater_than = var.checkpoints_delete_after_days
      }
    }
  }
}
