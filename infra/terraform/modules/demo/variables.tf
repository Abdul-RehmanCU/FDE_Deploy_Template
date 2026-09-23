variable "project_id" { type = string }
variable "region" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]+[0-9]$", var.region))
    error_message = "Demo region must be configured with a valid GCP region."
  }
}
variable "zone" {
  type = string
  validation {
    condition     = can(regex("^${var.region}-[a-z]$", var.zone))
    error_message = "Demo zone must belong to the configured region."
  }
}
variable "customer" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}[a-z0-9]$", var.customer))
    error_message = "customer must be a lowercase DNS-safe slug."
  }
}
variable "expiry_id" {
  type        = string
  description = "Unique run identity compiled into cleanup and resource labels."
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{3,40}$", var.expiry_id))
    error_message = "expiry_id must be a unique lowercase run identifier."
  }
}
variable "cluster_name" { type = string }
variable "machine_type" {
  type    = string
  default = "e2-standard-4"
  validation {
    condition     = var.machine_type == "e2-standard-4"
    error_message = "The cost-approved demo machine is exactly e2-standard-4."
  }
}
variable "node_disk_size_gb" {
  type    = number
  default = 30
  validation {
    condition     = var.node_disk_size_gb >= 20 && var.node_disk_size_gb <= 30
    error_message = "Demo boot disk must be between 20 and 30 GiB."
  }
}
variable "namespaces" {
  type    = set(string)
  default = ["staging", "production-demo"]
  validation {
    condition     = var.namespaces == toset(["staging", "production-demo"])
    error_message = "Demo must use exactly staging and production-demo namespaces."
  }
}
variable "labels" {
  type    = map(string)
  default = {}
}
