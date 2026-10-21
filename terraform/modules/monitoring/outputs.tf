output "log_analytics_workspace_id" {
  value = azurerm_log_analytics_workspace.this.id
}

output "log_analytics_workspace_name" {
  value = azurerm_log_analytics_workspace.this.name
}

output "data_alerts_action_group_id" {
  value = azurerm_monitor_action_group.data_alerts.id
}

output "mass_blob_delete_alert_id" {
  value = azurerm_monitor_scheduled_query_rules_alert_v2.mass_blob_delete.id
}
