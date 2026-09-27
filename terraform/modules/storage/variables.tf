variable "name_prefix" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "replication_type" {
  type    = string
  default = "LRS"
}

variable "allowed_ip_ranges" {
  type    = list(string)
  default = []
}

variable "subnet_id_for_vnet_rule" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "raw_zone_cool_tier_after_days" {
  description = "Days since last modification before raw/ zone blobs move to Cool tier. The raw zone is immutable/append-only, so it ages predictably and is a good tiering candidate."
  type        = number
  default     = 30
}

variable "raw_zone_archive_after_days" {
  description = "Days since last modification before raw/ zone blobs move to Archive tier."
  type        = number
  default     = 90
}

variable "checkpoints_delete_after_days" {
  description = "Days since last modification before transient Structured Streaming checkpoint blobs are deleted. Checkpoints have no long-term retention requirement, unlike raw/curated financial data."
  type        = number
  default     = 14
}
