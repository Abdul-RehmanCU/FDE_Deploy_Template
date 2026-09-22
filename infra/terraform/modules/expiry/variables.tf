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
variable "cluster_name" { type = string }
variable "artifact_repository" { type = string }
variable "bucket_names" { type = list(string) }
variable "disk_names" {
  type        = list(string)
  default     = []
  description = "Exact zonal persistent disk names discovered after workloads start."
}
variable "address_names" {
  type        = list(string)
  default     = []
  description = "Exact regional address names, normally empty because demo has no load balancer."
}
