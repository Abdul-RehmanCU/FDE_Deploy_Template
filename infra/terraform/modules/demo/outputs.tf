output "cluster" {
  value = {
    name     = google_container_cluster.demo.name
    location = google_container_cluster.demo.location
    endpoint = google_container_cluster.demo.endpoint
  }
  sensitive = true
}

output "artifact_repository" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "application_buckets" {
  value = { for name, bucket in google_storage_bucket.application : name => bucket.name }
}

output "runtime_service_accounts" {
  value = { for name, account in google_service_account.runtime : name => account.email }
}

output "secret_ids" {
  value       = sort([for secret in google_secret_manager_secret.runtime : secret.secret_id])
  description = "Secret containers only; versions are populated outside Terraform."
}
output "persistent_disk_volume_handles" {
  value = { for name, disk in google_compute_disk.data : name => "projects/${var.project_id}/zones/${var.zone}/disks/${disk.name}" }
}
