resource "azurerm_data_factory" "this" {
  name                = "adf-${var.name_prefix}"
  resource_group_name = var.resource_group_name
  location            = var.location

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

resource "azurerm_data_factory_linked_service_azure_blob_storage" "adls" {
  name             = "ls_adls_fraudplatform"
  data_factory_id  = azurerm_data_factory.this.id
  connection_string = "" # populated via Key Vault reference in practice; see linkedServices/ export
}

resource "azurerm_data_factory_linked_service_key_vault" "kv" {
  name            = "ls_key_vault"
  data_factory_id = azurerm_data_factory.this.id
  key_vault_id    = var.key_vault_id
}

resource "azurerm_data_factory_linked_custom_service" "databricks" {
  name            = "ls_databricks"
  data_factory_id = azurerm_data_factory.this.id
  type            = "AzureDatabricks"

  type_properties_json = jsonencode({
    domain           = var.databricks_workspace_url
    existingClusterId = "{{cluster_id_via_pipeline_parameter}}"
    authentication = {
      type = "SecureString"
      value = "@{linkedService().databricksToken}"
    }
  })
}

resource "azurerm_role_assignment" "adf_storage_contributor" {
  scope                = var.adls_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_data_factory.this.identity[0].principal_id
}
