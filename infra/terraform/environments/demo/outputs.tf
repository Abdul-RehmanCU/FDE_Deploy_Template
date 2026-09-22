output "cluster" {
  value     = module.demo.cluster
  sensitive = true
}
output "artifact_repository" { value = module.demo.artifact_repository }
output "application_buckets" { value = module.demo.application_buckets }
output "runtime_service_accounts" { value = module.demo.runtime_service_accounts }
output "secret_ids" { value = module.demo.secret_ids }
output "persistent_disk_volume_handles" { value = module.demo.persistent_disk_volume_handles }
