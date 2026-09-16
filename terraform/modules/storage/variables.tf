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
