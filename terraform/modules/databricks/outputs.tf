output "workspace_url" {
  value = "https://${azurerm_databricks_workspace.this.workspace_url}"
}

output "workspace_id" {
  value = azurerm_databricks_workspace.this.id
}

output "cluster_policy_id" {
  value = databricks_cluster_policy.etl_job_policy.id
}
