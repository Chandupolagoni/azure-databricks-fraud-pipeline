variable "environment" {
  description = "Deployment environment name (dev, staging, prod)"
  type        = string
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "eastus2"
}

variable "project_name" {
  description = "Short project name used as a naming prefix"
  type        = string
  default     = "fraudplatform"
}

variable "tags" {
  description = "Common resource tags"
  type        = map(string)
  default = {
    project     = "azure-databricks-fraud-pipeline"
    owner       = "data-engineering"
    cost_center = "risk-analytics"
  }
}

variable "adls_replication_type" {
  description = "ADLS Gen2 storage account replication type"
  type        = string
  default     = "ZRS"
}

variable "vnet_address_space" {
  description = "CIDR block for the platform VNet"
  type        = list(string)
  default     = ["10.20.0.0/16"]
}

variable "databricks_public_subnet_cidr" {
  type    = string
  default = "10.20.1.0/24"
}

variable "databricks_private_subnet_cidr" {
  type    = string
  default = "10.20.2.0/24"
}

variable "private_endpoint_subnet_cidr" {
  type    = string
  default = "10.20.3.0/24"
}

variable "databricks_sku" {
  description = "Databricks workspace SKU"
  type        = string
  default     = "premium"
}

variable "key_vault_sku" {
  type    = string
  default = "standard"
}

variable "allowed_ip_ranges" {
  description = "IP ranges allowed through storage/key vault firewalls (CI runners, corp VPN, etc.)"
  type        = list(string)
  default     = []
}

variable "snowflake_account" {
  description = "Snowflake account identifier, used only to tag/document the external stage config (no credentials stored here)"
  type        = string
  default     = "orgname-fraudplatform"
}
