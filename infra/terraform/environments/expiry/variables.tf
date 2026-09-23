variable "project_id" { type = string }
variable "project_number" { type = string }
variable "region" {
  type = string
}
variable "zone" {
  type = string
}
variable "expiry_id" { type = string }
variable "expires_at" { type = string }
variable "cluster_name" { type = string }
variable "artifact_repository" { type = string }
variable "bucket_names" { type = list(string) }
variable "disk_names" {
  type    = list(string)
  default = []
}
variable "address_resources" {
  type = list(object({
    name               = string
    creation_timestamp = string
  }))
  default = []
}
