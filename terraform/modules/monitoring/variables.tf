variable "name_prefix" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "storage_account_id" {
  description = "Resource ID of the ADLS Gen2 storage account (module.storage.storage_account_id) to attach blob-service audit logging to."
  type        = string
}

variable "databricks_workspace_id" {
  description = "Resource ID of the Databricks workspace (module.databricks.workspace_id) to attach workspace-level audit-log diagnostic settings to."
  type        = string
}

variable "key_vault_id" {
  description = "Resource ID of the Key Vault (module.key_vault.key_vault_id) to attach secret-access audit-log diagnostic settings to."
  type        = string
}

variable "log_retention_days" {
  description = "Days Log Analytics retains ingested audit logs. Financial-services audit trails typically require longer retention in prod than dev."
  type        = number
  default     = 90
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "mass_delete_alert_threshold" {
  description = "Number of successful StorageDelete operations against the ADLS account allowed within one evaluation window (see mass_delete_alert_window_minutes) before the mass-delete alert fires. Set lower in prod than dev, since prod raw/curated data is rarely deleted in bulk by legitimate jobs."
  type        = number
  default     = 50
}

variable "mass_delete_alert_window_minutes" {
  description = "Evaluation window, in minutes, the mass-delete alert's StorageDelete count is summed over."
  type        = number
  default     = 5
}

variable "alert_notification_emails" {
  description = "Email addresses to notify when a monitoring alert (e.g. mass blob delete) fires. Left empty by default and wired in at deploy time (e.g. via -var or a CI secret) rather than committed, since on-call distribution lists change independently of infrastructure code."
  type        = list(string)
  default     = []
}
