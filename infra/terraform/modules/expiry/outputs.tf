output "workflow_name" { value = google_workflows_workflow.cleanup.name }
output "scheduler_jobs" { value = { for name, job in google_cloud_scheduler_job.expiry : name => job.name } }
output "scheduler_schedules" {
  value       = { for name, job in google_cloud_scheduler_job.expiry : name => job.schedule }
  description = "Exact UTC cron triggers rendered from the minute-aligned expiry timestamp."
}
output "scheduler_invocation_scope" {
  value       = "Dedicated Scheduler-only service account with project-level roles/workflows.invoker"
  description = "Workflows does not support resource-name IAM conditions; deletion authority stays on the separate workflow identity."
}
output "manifest_sha" { value = local.manifest_sha }
output "compiled_manifest" {
  value       = local.manifest
  description = "Exact allowlist to preserve with private cleanup evidence."
}
