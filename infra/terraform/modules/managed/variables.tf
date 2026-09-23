variable "project_id" { type = string }
variable "region" {
  type = string
}
variable "customer" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}[a-z0-9]$", var.customer))
    error_message = "customer must be a lowercase DNS-safe slug."
  }
}
variable "environment" {
  type = string
  validation {
    condition     = var.environment == "production"
    error_message = "Managed profile is only valid for an explicit production environment."
  }
}
variable "cluster_name" { type = string }
variable "domain" {
  type = string
  validation {
    condition     = can(regex("^[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$", var.domain))
    error_message = "Managed profile requires a valid customer-controlled DNS name."
  }
}
variable "labels" {
  type    = map(string)
  default = {}
}
