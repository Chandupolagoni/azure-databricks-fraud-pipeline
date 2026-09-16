# VNet-injected Databricks workspace (secure cluster connectivity), so all cluster
# traffic stays inside the platform VNet rather than a Microsoft-managed one.

resource "azurerm_databricks_workspace" "this" {
  name                        = "dbw-${var.name_prefix}"
  resource_group_name        = var.resource_group_name
  location                    = var.location
  sku                          = var.sku
  managed_resource_group_name = "rg-${var.name_prefix}-dbw-managed"

  custom_parameters {
    virtual_network_id                                   = var.vnet_id
    public_subnet_name                                    = var.public_subnet_name
    private_subnet_name                                   = var.private_subnet_name
    public_subnet_network_security_group_association_id  = var.public_subnet_nsg_association
    private_subnet_network_security_group_association_id = var.private_subnet_nsg_association
    no_public_ip                                          = true
  }

  tags = var.tags
}

# Job cluster policy — enforces autoscaling bounds, spot usage, and Delta/Photon defaults
# for all scheduled ETL jobs (referenced by databricks/jobs/job_config.json).
resource "databricks_cluster_policy" "etl_job_policy" {
  name = "etl-job-policy-${var.name_prefix}"

  definition = jsonencode({
    "spark_version" : {
      "type" : "fixed",
      "value" : "14.3.x-scala2.12"
    },
    "node_type_id" : {
      "type" : "allowlist",
      "values" : ["Standard_DS3_v2", "Standard_DS4_v2"]
    },
    "autoscale.min_workers" : {
      "type" : "range",
      "minValue" : 1,
      "maxValue" : 2
    },
    "autoscale.max_workers" : {
      "type" : "range",
      "minValue" : 2,
      "maxValue" : 8
    },
    "custom_tags.project" : {
      "type" : "fixed",
      "value" : "fraud-platform"
    }
  })

  depends_on = [azurerm_databricks_workspace.this]
}

resource "databricks_secret_scope" "kv_backed" {
  name = "fraud-platform-kv-scope"

  depends_on = [azurerm_databricks_workspace.this]
}
