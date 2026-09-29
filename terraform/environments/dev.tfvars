environment  = "dev"
location     = "eastus2"
project_name = "fraudplatform"

adls_replication_type = "LRS"

# Dev data churns fast and isn't retained for compliance, so tier/delete sooner than prod
raw_zone_cool_tier_after_days = 14
raw_zone_archive_after_days   = 30
checkpoints_delete_after_days = 7

# Dev audit logs don't need long retention
log_analytics_retention_days = 30

vnet_address_space              = ["10.20.0.0/16"]
databricks_public_subnet_cidr   = "10.20.1.0/24"
databricks_private_subnet_cidr  = "10.20.2.0/24"
private_endpoint_subnet_cidr    = "10.20.3.0/24"

databricks_sku = "premium"
key_vault_sku  = "standard"

tags = {
  project     = "azure-databricks-fraud-pipeline"
  owner       = "data-engineering"
  environment = "dev"
  cost_center = "risk-analytics"
}
