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

# Dev workloads (synthetic data refreshes, test fixture teardown) routinely delete
# more blobs at once than prod ever should, so the mass-delete alert threshold is looser
mass_delete_alert_threshold = 200

# Dev pipeline runs include intentional failure-path testing (bad manifest fixtures,
# forced linked-service errors), so a handful of failures per window is routine here,
# unlike prod where any failure should page immediately (adf_pipeline_failure_alert_threshold default of 0)
adf_pipeline_failure_alert_threshold = 3

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
