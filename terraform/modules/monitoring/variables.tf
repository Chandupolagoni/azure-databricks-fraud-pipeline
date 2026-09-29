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

variable "log_retention_days" {
  description = "Days Log Analytics retains ingested audit logs. Financial-services audit trails typically require longer retention in prod than dev."
  type        = number
  default     = 90
}

variable "tags" {
  type    = map(string)
  default = {}
}
