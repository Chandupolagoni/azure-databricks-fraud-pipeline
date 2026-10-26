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

# Key Vault secret-access audit logs into the same shared Log Analytics workspace. Every
# Snowflake/ADLS credential the platform's Databricks jobs and ADF linked services resolve
# at runtime comes through this Key Vault (fraud-platform-kv-scope, modules/key-vault), so
# "who read or wrote which secret, and when" is exactly the kind of access financial-services
# audit requirements expect to be queryable - without this, the data-plane (storage) and
# compute-plane (databricks_workspace) trails above existed, but the credentials backing
# both of them had none of their own.
resource "azurerm_monitor_diagnostic_setting" "key_vault" {
  name                       = "diag-${var.name_prefix}-key-vault"
  target_resource_id         = var.key_vault_id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id

  enabled_log {
    category = "AuditEvent"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}

# Notification target for log-based alerts defined below. Kept as a single shared action
# group (rather than one per alert) since this module currently has one alert, and any
# future log-based alert on this workspace can reuse it.
resource "azurerm_monitor_action_group" "data_alerts" {
  name                = "ag-${var.name_prefix}-data-alerts"
  resource_group_name = var.resource_group_name
  short_name          = "fraudalrt"

  dynamic "email_receiver" {
    for_each = var.alert_notification_emails
    content {
      name                    = "email-${replace(email_receiver.value, "/[^a-zA-Z0-9]/", "-")}"
      email_address           = email_receiver.value
      use_common_alert_schema = true
    }
  }

  tags = var.tags
}

# Log-based alert on the StorageDelete diagnostic logs ingested above. The diagnostic
# setting on its own only makes delete activity *queryable after the fact* — an
# investigator reviewing it after a raw/curated zone has already been wiped is too slow
# to matter for a financial platform. This closes that gap by firing in near-real-time
# when successful blob deletes against the storage account spike past a normal-operations
# baseline, catching an accidental mass delete or a compromised credential/job before it
# runs to completion.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "mass_blob_delete" {
  name                = "alert-${var.name_prefix}-mass-blob-delete"
  resource_group_name = var.resource_group_name
  location            = var.location

  evaluation_frequency = "PT${var.mass_delete_alert_window_minutes}M"
  window_duration      = "PT${var.mass_delete_alert_window_minutes}M"
  scopes               = [azurerm_log_analytics_workspace.this.id]
  severity             = 1

  criteria {
    query = <<-QUERY
      AzureDiagnostics
      | where ResourceProvider == "MICROSOFT.STORAGE"
      | where Category == "StorageDelete"
      | where StatusText == "Success"
      | summarize DeleteCount = count()
    QUERY

    time_aggregation_method = "Count"
    threshold                = var.mass_delete_alert_threshold
    operator                 = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.data_alerts.id]
  }

  description  = "Successful StorageDelete operations against the ADLS storage account exceeded ${var.mass_delete_alert_threshold} within a ${var.mass_delete_alert_window_minutes}-minute window."
  display_name = "Mass blob delete detected — ${var.name_prefix}"
  enabled      = true
  tags         = var.tags
}
