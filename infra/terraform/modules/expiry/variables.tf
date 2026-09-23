variable "project_id" { type = string }
variable "project_number" { type = string }
variable "region" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]+[0-9]$", var.region))
    error_message = "Expiry region must be configured with a valid GCP region."
  }
}
variable "zone" {
  type = string
  validation {
    condition     = can(regex("^${var.region}-[a-z]$", var.zone))
    error_message = "Expiry zone must belong to the configured region."
  }
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
    condition = (
      can(formatdate("YYYY-MM-DD'T'hh:mm:ss'Z'", var.expires_at)) &&
      can(regex("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:00Z$", var.expires_at))
    )
    error_message = "expires_at must be a UTC RFC3339 timestamp on an exact minute (:00Z)."
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
  description = "Exact disk names predeclared in the workflow before GKE or disks exist."
  validation {
    condition = (
      length(var.disk_names) == length(distinct(var.disk_names)) &&
      var.disk_names == sort(var.disk_names) &&
      alltrue([for name in var.disk_names : can(regex("^[a-z][a-z0-9-]{1,61}[a-z0-9]$", name))])
    )
    error_message = "disk_names must be sorted unique exact names."
  }
}
variable "address_resources" {
  type = list(object({
    name               = string
    creation_timestamp = string
  }))
  default     = []
  description = "Exact regional address names and immutable creation timestamps; normally empty."
  validation {
    condition = (
      length(var.address_resources) == length(distinct([for resource in var.address_resources : resource.name])) &&
      join(",", [for resource in var.address_resources : resource.name]) == join(",", sort([for resource in var.address_resources : resource.name])) &&
      alltrue([for resource in var.address_resources :
        can(regex("^[a-z][a-z0-9-]{1,61}[a-z0-9]$", resource.name)) && can(formatdate("YYYY", resource.creation_timestamp))
      ])
    )
    error_message = "address_resources must contain unique exact names and RFC3339 creation timestamps."
  }
}
