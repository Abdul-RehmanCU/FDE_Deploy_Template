variable "project_id" { type = string }
variable "region" {
  type    = string
  default = "northamerica-northeast1"
  validation {
    condition     = var.region == "northamerica-northeast1"
    error_message = "Demo resources must remain in Montréal."
  }
}
variable "zone" {
  type    = string
  default = "northamerica-northeast1-a"
  validation {
    condition     = var.zone == "northamerica-northeast1-a"
    error_message = "The approved demo zone is northamerica-northeast1-a."
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
