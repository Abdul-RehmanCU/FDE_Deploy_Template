variable "project_id" { type = string }
variable "region" {
  type = string
}
variable "customer" { type = string }
variable "environment" {
  type    = string
  default = "production"
}
variable "cluster_name" { type = string }
variable "domain" { type = string }
variable "labels" {
  type    = map(string)
  default = {}
}
