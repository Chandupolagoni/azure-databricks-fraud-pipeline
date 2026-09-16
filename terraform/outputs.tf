output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "adls_storage_account_name" {
  value = module.storage.storage_account_name
}

output "adls_raw_container" {
  value = module.storage.raw_container_name
}

output "adls_curated_container" {
  value = module.storage.curated_container_name
}

output "databricks_workspace_url" {
  value = module.databricks.workspace_url
}

output "databricks_workspace_id" {
  value = module.databricks.workspace_id
}

output "key_vault_uri" {
  value = module.key_vault.key_vault_uri
}

output "data_factory_name" {
  value = module.adf.data_factory_name
}
