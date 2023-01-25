# Required configurations
variable "base" {
  type        = any
  description = "Base configurations"
}

variable "nxs_config" {
  type        = any
  description = "Nxs configurations"
}

# deprecated
variable "location" {
  type        = string
  description = "Location of the resource group"
}

variable "rg_name" {
  type        = string
  description = "Name of the resource group"
}

variable "admin_group_object_id" {
  type        = string
  description = "Object ID of the Pixie admin group"
}

variable "subscription_id" {
  type        = string
  description = "Azure subscription id"
}

variable "tenant_id" {
  type        = string
  description = "Azure tenant id"
}
