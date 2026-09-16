output "data_factory_name" {
  value = azurerm_data_factory.this.name
}

output "data_factory_id" {
  value = azurerm_data_factory.this.id
}

output "data_factory_principal_id" {
  value = azurerm_data_factory.this.identity[0].principal_id
}
