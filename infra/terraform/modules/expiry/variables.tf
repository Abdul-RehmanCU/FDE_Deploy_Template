variable "project_id" { type = string }
variable "project_number" { type = string }
variable "region" {
  type    = string
  default = "northamerica-northeast1"
  validation {
    condition     = var.region == "northamerica-northeast1"
    error_message = "Expiry workflow must remain in Montréal."
  }
}
variable "zone" {
  type    = string
  default = "northamerica-northeast1-a"
}
variable "expiry_id" {
  type        = string
  description = "Unique identifier shared by this one demo and its evidence."
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{3,40}$", var.expiry_id))
    error_message = "expiry_id must be a lowercase safe identifier."
  }
}
variable "expires_at" {
  type        = string
  description = "RFC3339 deadline, no more than four hours after paid provisioning begins."
  validation {
    condition     = can(formatdate("YYYY-MM-DD'T'hh:mm:ss'Z'", var.expires_at))
    error_message = "expires_at must be an RFC3339 timestamp."
  }
}
variable "cluster_name" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,38}[a-z0-9]$", var.cluster_name))
    error_message = "cluster_name must be a lowercase GKE resource name."
  }
}
variable "artifact_repository" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,61}[a-z0-9]$", var.artifact_repository))
    error_message = "artifact_repository must be a lowercase repository ID."
  }
}
variable "bucket_names" {
  type = list(string)
  validation {
    condition = (
      length(var.bucket_names) == length(distinct(var.bucket_names)) &&
      alltrue([for name in var.bucket_names : can(regex("^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$", name))])
    )
    error_message = "bucket_names must be unique valid exact bucket names."
  }
}
variable "disk_names" {
  type        = list(string)
  default     = []
  description = "Exact zonal persistent disk names discovered after workloads start."
  validation {
    condition = (
      length(var.disk_names) == length(distinct(var.disk_names)) &&
      alltrue([for name in var.disk_names : can(regex("^[a-z][a-z0-9-]{1,61}[a-z0-9]$", name))])
    )
    error_message = "disk_names must be unique valid exact disk names."
  }
}
variable "address_names" {
  type        = list(string)
  default     = []
  description = "Exact regional address names, normally empty because demo has no load balancer."
  validation {
    condition = (
      length(var.address_names) == length(distinct(var.address_names)) &&
      alltrue([for name in var.address_names : can(regex("^[a-z][a-z0-9-]{1,61}[a-z0-9]$", name))])
    )
    error_message = "address_names must be unique valid exact address names."
  }
}
