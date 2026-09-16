output "vnet_id" {
  value = azurerm_virtual_network.this.id
}

output "databricks_public_subnet_name" {
  value = azurerm_subnet.databricks_public.name
}

output "databricks_private_subnet_name" {
  value = azurerm_subnet.databricks_private.name
}

output "private_endpoint_subnet_id" {
  value = azurerm_subnet.private_endpoints.id
}

output "public_subnet_nsg_association_id" {
  value = azurerm_subnet_network_security_group_association.public.id
}

output "private_subnet_nsg_association_id" {
  value = azurerm_subnet_network_security_group_association.private.id
}
