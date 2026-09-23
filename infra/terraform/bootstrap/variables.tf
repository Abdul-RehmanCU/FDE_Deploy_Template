variable "project_id" {
  description = "Dedicated GCP project for this installation."
  type        = string
}

variable "region" {
  description = "Privately configured region used by state and identities."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]+[0-9]$", var.region))
    error_message = "Supply a valid GCP region."
  }
}

variable "github_repository" {
  description = "GitHub owner/repository permitted to exchange OIDC tokens."
  type        = string
  default     = "Abdul-RehmanCU/FDE_Deploy_Template"

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "github_repository must use owner/repository form."
  }
}

variable "state_bucket_name" {
  description = "Globally unique Terraform state bucket name."
  type        = string
}
