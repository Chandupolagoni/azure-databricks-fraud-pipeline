locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

resource "azurerm_resource_group" "this" {
  name     = "rg-${local.name_prefix}"
  location = var.location
  tags     = var.tags
}

module "networking" {
  source = "./modules/networking"

  name_prefix                    = local.name_prefix
  resource_group_name            = azurerm_resource_group.this.name
  location                       = azurerm_resource_group.this.location
  vnet_address_space              = var.vnet_address_space
  databricks_public_subnet_cidr  = var.databricks_public_subnet_cidr
  databricks_private_subnet_cidr = var.databricks_private_subnet_cidr
  private_endpoint_subnet_cidr   = var.private_endpoint_subnet_cidr
  tags                            = var.tags
}

module "storage" {
  source = "./modules/storage"

  name_prefix          = local.name_prefix
  resource_group_name  = azurerm_resource_group.this.name
  location             = azurerm_resource_group.this.location
  replication_type     = var.adls_replication_type
  allowed_ip_ranges    = var.allowed_ip_ranges
  subnet_id_for_vnet_rule = module.networking.private_endpoint_subnet_id
  tags                 = var.tags
}

module "key_vault" {
  source = "./modules/key-vault"

  name_prefix         = local.name_prefix
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  sku_name            = var.key_vault_sku
  allowed_ip_ranges   = var.allowed_ip_ranges
  tags                = var.tags
}

module "databricks" {
  source = "./modules/databricks"

  name_prefix                    = local.name_prefix
  resource_group_name            = azurerm_resource_group.this.name
  location                       = azurerm_resource_group.this.location
  sku                             = var.databricks_sku
  vnet_id                         = module.networking.vnet_id
  public_subnet_name              = module.networking.databricks_public_subnet_name
  private_subnet_name             = module.networking.databricks_private_subnet_name
  public_subnet_nsg_association   = module.networking.public_subnet_nsg_association_id
  private_subnet_nsg_association  = module.networking.private_subnet_nsg_association_id
  tags                             = var.tags
}

module "adf" {
  source = "./modules/adf"

  name_prefix          = local.name_prefix
  resource_group_name  = azurerm_resource_group.this.name
  location             = azurerm_resource_group.this.location
  adls_account_id      = module.storage.storage_account_id
  databricks_workspace_url = module.databricks.workspace_url
  key_vault_id         = module.key_vault.key_vault_id
  tags                 = var.tags
}
