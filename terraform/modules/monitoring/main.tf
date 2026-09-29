# Centralized audit logging for the platform's data-plane resources.
#
# Financial-services data handling requires an auditable trail of who read, wrote, or
# deleted data in the ADLS Gen2 storage account (see architecture.md's Storage section) —
# access controls (firewall + VNet rules, private endpoints) restrict *who can reach* the
# account, but don't by themselves produce a queryable log of what happened. This module
# provisions the Log Analytics workspace and wires the storage account's blob-service
# diagnostic logs into it, kept as its own module (rather than folded into the storage
# module) so other resources can send diagnostics to the same shared workspace later
# without duplicating the workspace resource.

resource "azurerm_log_analytics_workspace" "this" {
  name                = "law-${var.name_prefix}"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "PerGB2018"
  retention_in_days   = var.log_retention_days

  tags = var.tags
}

# Blob read/write/delete audit logs plus transaction metrics for the ADLS storage account.
# Diagnostic settings for the account's other services (queue/table/file) aren't added
# since the platform only uses the blob/ADLS Gen2 surface.
resource "azurerm_monitor_diagnostic_setting" "storage_blob" {
  name                       = "diag-${var.name_prefix}-storage-blob"
  target_resource_id         = "${var.storage_account_id}/blobServices/default"
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id

  enabled_log {
    category = "StorageRead"
  }

  enabled_log {
    category = "StorageWrite"
  }

  enabled_log {
    category = "StorageDelete"
  }

  metric {
    category = "Transaction"
    enabled  = true
  }
}
