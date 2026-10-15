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

# Workspace-level audit logs for the Databricks workspace, sent to the same shared
# Log Analytics workspace as the storage account's blob logs above (rather than a second
# workspace) so an investigator can correlate "who touched the data" with "who touched the
# compute/notebooks that produced or read it" in one place. Scoped to the categories that
# matter for an audit trail rather than every category Databricks exposes:
#   - accounts: login, user/group/permission changes on the workspace itself
#   - clusters: cluster create/edit/delete/resize, since job clusters run under the
#     etl-job-policy defined in modules/databricks and any drift from that policy should
#     be traceable
#   - notebook: notebook command/run history, covering ad-hoc access to Silver/Gold data
#     that doesn't go through the scheduled job_config.json path
#   - secrets: reads/writes against the fraud-platform-kv-scope secret scope backing the
#     Key Vault-sourced Snowflake/ADLS credentials (modules/databricks, modules/key-vault)
#   - workspace: workspace object create/delete/rename (notebooks, folders, repos)
resource "azurerm_monitor_diagnostic_setting" "databricks_workspace" {
  name                       = "diag-${var.name_prefix}-databricks"
  target_resource_id         = var.databricks_workspace_id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id

  enabled_log {
    category = "accounts"
  }

  enabled_log {
    category = "clusters"
  }

  enabled_log {
    category = "notebook"
  }

  enabled_log {
    category = "secrets"
  }

  enabled_log {
    category = "workspace"
  }
}
