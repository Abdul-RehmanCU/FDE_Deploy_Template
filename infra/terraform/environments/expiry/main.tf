module "expiry" {
  source              = "../../modules/expiry"
  project_id          = var.project_id
  project_number      = var.project_number
  region              = var.region
  zone                = var.zone
  expiry_id           = var.expiry_id
  expires_at          = var.expires_at
  cluster_name        = var.cluster_name
  artifact_repository = var.artifact_repository
  bucket_names        = var.bucket_names
  disk_resources      = var.disk_resources
  address_resources   = var.address_resources
}
