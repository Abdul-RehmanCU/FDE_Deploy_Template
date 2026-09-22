module "managed" {
  source       = "../../modules/managed"
  project_id   = var.project_id
  region       = var.region
  customer     = var.customer
  environment  = var.environment
  cluster_name = var.cluster_name
  domain       = var.domain
  labels       = var.labels
}
