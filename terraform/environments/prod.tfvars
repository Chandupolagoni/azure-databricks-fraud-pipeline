environment  = "prod"
location     = "eastus2"
project_name = "fraudplatform"

adls_replication_type = "ZRS"

# Financial raw-zone data: keep it Hot longer before tiering down, matching data-handling requirements
raw_zone_cool_tier_after_days = 30
raw_zone_archive_after_days   = 90
checkpoints_delete_after_days = 14

vnet_address_space              = ["10.30.0.0/16"]
databricks_public_subnet_cidr   = "10.30.1.0/24"
databricks_private_subnet_cidr  = "10.30.2.0/24"
private_endpoint_subnet_cidr    = "10.30.3.0/24"

databricks_sku = "premium"
key_vault_sku  = "premium"

tags = {
  project     = "azure-databricks-fraud-pipeline"
  owner       = "data-engineering"
  environment = "prod"
  cost_center = "risk-analytics"
}
