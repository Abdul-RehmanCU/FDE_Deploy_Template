output "state_bucket" {
  value = google_storage_bucket.terraform_state.name
}

output "workload_identity_provider" {
  value = { for name, provider in google_iam_workload_identity_pool_provider.github : name => provider.name }
}

output "service_accounts" {
  value = { for name, account in google_service_account.automation : name => account.email }
}

output "automation_scope_notes" {
  value = {
    build   = "main branch and protected demo-build environment; PR validation has no cloud writer"
    infra   = "dedicated demo project Terraform control; broad only inside project"
    deploy  = "GKE workload deployment and Artifact Registry pull only"
    cleanup = "protected demo-cleanup environment; broad Terraform destroy in dedicated project, distinct from exact-manifest expiry workflow identity"
  }
}
