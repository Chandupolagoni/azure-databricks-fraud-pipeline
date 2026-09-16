variable "name_prefix" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "sku_name" {
  type    = string
  default = "standard"
}

variable "allowed_ip_ranges" {
  type    = list(string)
  default = []
}

variable "snowflake_account_placeholder" {
  description = "Non-secret placeholder value; real credentials are injected via CI secrets, not Terraform state"
  type        = string
  default     = "CHANGE_ME_VIA_CI_SECRET"
}

variable "tags" {
  type    = map(string)
  default = {}
}
