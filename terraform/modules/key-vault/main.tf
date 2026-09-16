data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "this" {
  name                       = substr("kv-${var.name_prefix}", 0, 24)
  resource_group_name        = var.resource_group_name
  location                   = var.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = var.sku_name
  purge_protection_enabled   = true
  soft_delete_retention_days = 90

  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"
    ip_rules       = var.allowed_ip_ranges
  }

  tags = var.tags
}

resource "azurerm_key_vault_access_policy" "terraform_deployer" {
  key_vault_id = azurerm_key_vault.this.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  secret_permissions = ["Get", "List", "Set", "Delete", "Purge", "Recover"]
}

# Placeholders — actual secret values are set out-of-band (CI secret store / az cli),
# never committed to source control.
resource "azurerm_key_vault_secret" "snowflake_account" {
  name         = "snowflake-account"
  value        = var.snowflake_account_placeholder
  key_vault_id = azurerm_key_vault.this.id

  depends_on = [azurerm_key_vault_access_policy.terraform_deployer]
}
