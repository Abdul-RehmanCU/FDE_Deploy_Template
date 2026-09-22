variable "project_id" { type = string }
variable "customer" { type = string }
variable "expiry_id" { type = string }
variable "region" {
  type    = string
  default = "northamerica-northeast1"
}
variable "zone" {
  type    = string
  default = "northamerica-northeast1-a"
}
variable "cluster_name" { type = string }
variable "machine_type" {
  type    = string
  default = "e2-standard-4"
}
variable "node_disk_size_gb" {
  type    = number
  default = 30
}
variable "labels" {
  type    = map(string)
  default = {}
}
