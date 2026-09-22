output "workflow_name" { value = google_workflows_workflow.cleanup.name }
output "scheduler_job" { value = google_cloud_scheduler_job.expiry.name }
output "manifest_sha" { value = local.manifest_sha }
output "compiled_manifest" {
  value       = local.manifest
  description = "Exact allowlist to preserve with private cleanup evidence."
}
