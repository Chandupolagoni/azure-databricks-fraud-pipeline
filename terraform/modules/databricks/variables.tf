variable "name_prefix" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "sku" {
  type    = string
  default = "premium"
}

variable "vnet_id" {
  type = string
}

variable "public_subnet_name" {
  type = string
}

variable "private_subnet_name" {
  type = string
}

variable "public_subnet_nsg_association" {
  type = string
}

variable "private_subnet_nsg_association" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
