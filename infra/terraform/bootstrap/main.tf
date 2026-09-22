locals {
  required_services = toset([
    "artifactregistry.googleapis.com",
    "cloudasset.googleapis.com",
    "cloudscheduler.googleapis.com",
    "compute.googleapis.com",
    "container.googleapis.com",
    "iamcredentials.googleapis.com",
    "secretmanager.googleapis.com",
    "sts.googleapis.com",
    "workflowexecutions.googleapis.com",
    "workflows.googleapis.com",
  ])
  identities = {
    build   = "Build and publish immutable images"
    infra   = "Plan and apply customer infrastructure"
    deploy  = "Release immutable images to GKE"
    cleanup = "Run allowlisted demo expiry cleanup"
  }
}

resource "google_project_service" "required" {
  for_each           = local.required_services
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

resource "google_storage_bucket" "terraform_state" {
  name                        = var.state_bucket_name
  project                     = var.project_id
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning { enabled = true }

  lifecycle_rule {
    condition { num_newer_versions = 5 }
    action { type = "Delete" }
  }

  labels = {
    application = "fde-template"
    purpose     = "terraform-state"
    managed-by  = "terraform"
  }
}

resource "google_service_account" "automation" {
  for_each     = local.identities
  project      = var.project_id
  account_id   = "fde-${each.key}"
  display_name = each.value
}

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "fde-github"
  display_name              = "FDE GitHub Actions"
  description               = "Keyless GitHub Actions federation for the FDE repository"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "fde-repository"
  display_name                       = "FDE repository"

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.repository"       = "assertion.repository"
    "attribute.ref"              = "assertion.ref"
    "attribute.environment"      = "assertion.environment"
    "attribute.repository_owner" = "assertion.repository_owner"
  }
  attribute_condition = "assertion.repository == '${var.github_repository}' && assertion.repository_owner == 'Abdul-RehmanCU'"

  oidc { issuer_uri = "https://token.actions.githubusercontent.com" }
}

resource "google_service_account_iam_member" "github_federation" {
  for_each           = google_service_account.automation
  service_account_id = each.value.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

resource "google_storage_bucket_iam_member" "infra_state" {
  bucket = google_storage_bucket.terraform_state.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.automation["infra"].email}"
}
