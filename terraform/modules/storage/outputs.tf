output "storage_account_id" {
  value = azurerm_storage_account.adls.id
}

output "storage_account_name" {
  value = azurerm_storage_account.adls.name
}

output "raw_container_name" {
  value = azurerm_storage_data_lake_gen2_filesystem.raw.name
}

output "curated_container_name" {
  value = azurerm_storage_data_lake_gen2_filesystem.curated.name
}

output "checkpoints_container_name" {
  value = azurerm_storage_data_lake_gen2_filesystem.checkpoints.name
}
