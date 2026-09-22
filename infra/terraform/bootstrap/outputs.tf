output "state_bucket" {
  value = google_storage_bucket.terraform_state.name
}

output "workload_identity_provider" {
  value = { for name, provider in google_iam_workload_identity_pool_provider.github : name => provider.name }
}

output "service_accounts" {
  value = { for name, account in google_service_account.automation : name => account.email }
}
