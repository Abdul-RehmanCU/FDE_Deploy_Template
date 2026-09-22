module "demo" {
  source            = "../../modules/demo"
  project_id        = var.project_id
  customer          = var.customer
  expiry_id         = var.expiry_id
  region            = var.region
  zone              = var.zone
  cluster_name      = var.cluster_name
  machine_type      = var.machine_type
  node_disk_size_gb = var.node_disk_size_gb
  labels            = var.labels
}
