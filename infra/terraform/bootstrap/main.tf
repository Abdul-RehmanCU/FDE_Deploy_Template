locals {
  # The owner CLI enables Resource Manager before init/import/refresh. Resource
  # dependencies below order creation, but cannot protect a prior state refresh.
  github_owner = split("/", var.github_repository)[0]
  # Deleted WIF pool IDs remain reserved. A fresh state bucket gives a fresh
  # bootstrap generation without reviving deleted identities.
  workload_identity_pool_id = "fde-gh-${substr(sha256(var.state_bucket_name), 0, 12)}"
  required_services = toset([
    "artifactregistry.googleapis.com",
    "cloudasset.googleapis.com",
    "cloudresourcemanager.googleapis.com",
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
  automation_roles = {
    build = toset([
      "roles/artifactregistry.writer",
    ])
    infra = toset([
      "roles/artifactregistry.admin",
      "roles/cloudscheduler.admin",
      "roles/compute.networkAdmin",
      "roles/compute.securityAdmin",
      "roles/container.admin",
      "roles/iam.roleAdmin",
      "roles/iam.serviceAccountAdmin",
      "roles/iam.workloadIdentityPoolAdmin",
      "roles/resourcemanager.projectIamAdmin",
      "roles/serviceusage.serviceUsageAdmin",
      "roles/compute.storageAdmin",
      "roles/secretmanager.admin",
      "roles/storage.admin",
      "roles/workflows.admin",
    ])
    deploy = toset([
      "roles/artifactregistry.reader",
      "roles/container.developer",
    ])
    cleanup = toset([
      "roles/artifactregistry.admin",
      "roles/cloudasset.viewer",
      "roles/cloudscheduler.admin",
      "roles/compute.networkAdmin",
      "roles/compute.securityAdmin",
      "roles/container.admin",
      "roles/iam.roleAdmin",
      "roles/iam.serviceAccountAdmin",
      "roles/iam.workloadIdentityPoolAdmin",
      "roles/resourcemanager.projectIamAdmin",
      "roles/serviceusage.serviceUsageAdmin",
      "roles/compute.storageAdmin",
      "roles/secretmanager.admin",
      "roles/storage.admin",
      "roles/workflows.admin",
    ])
  }
  automation_role_bindings = merge([
    for identity, roles in local.automation_roles : {
      for role in roles : "${identity}:${role}" => { identity = identity, role = role }
    }
  ]...)
}

resource "google_project_service" "required" {
  for_each           = local.required_services
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

resource "google_storage_bucket" "terraform_state" {
  #checkov:skip=CKV_GCP_62: This short-lived versioned state bucket has no separate log sink; owner finalization exports evidence and deletes every generation.
  name                        = var.state_bucket_name
  project                     = var.project_id
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning { enabled = true }
  soft_delete_policy { retention_duration_seconds = 0 }

  lifecycle_rule {
    condition { num_newer_versions = 5 }
    action { type = "Delete" }
  }

  labels = {
    application = "fde-template"
    purpose     = "terraform-state"
    managed-by  = "terraform"
  }

  depends_on = [google_project_service.required]
}

resource "google_service_account" "automation" {
  for_each     = local.identities
  project      = var.project_id
  account_id   = "fde-${each.key}"
  display_name = each.value

  depends_on = [google_project_service.required]
}

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = local.workload_identity_pool_id
  display_name              = "FDE GitHub Actions"
  description               = "Keyless GitHub Actions federation for the FDE repository"

  depends_on = [google_project_service.required]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  #checkov:skip=CKV_GCP_125: Conditions bind exact repository owner/repo, main ref, and protected GitHub environment; the scanner does not evaluate the for_each CEL map.
  for_each = {
    build   = "assertion.repository == '${var.github_repository}' && assertion.repository_owner == '${local.github_owner}' && assertion.ref == 'refs/heads/main' && assertion.environment == 'demo-build'"
    infra   = "assertion.repository == '${var.github_repository}' && assertion.repository_owner == '${local.github_owner}' && assertion.ref == 'refs/heads/main' && assertion.environment == 'demo-infrastructure'"
    deploy  = "assertion.repository == '${var.github_repository}' && assertion.repository_owner == '${local.github_owner}' && assertion.ref == 'refs/heads/main' && assertion.environment in ['demo-staging', 'demo-prod']"
    cleanup = "assertion.repository == '${var.github_repository}' && assertion.repository_owner == '${local.github_owner}' && assertion.ref == 'refs/heads/main' && assertion.environment == 'demo-cleanup'"
  }
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "fde-${each.key}"
  display_name                       = "FDE ${each.key} identity"

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.automation"       = "'${each.key}'"
    "attribute.repository"       = "assertion.repository"
    "attribute.ref"              = "assertion.ref"
    "attribute.environment"      = "has(assertion.environment) ? assertion.environment : ''"
    "attribute.event_name"       = "assertion.event_name"
    "attribute.repository_owner" = "assertion.repository_owner"
  }
  attribute_condition = each.value

  oidc { issuer_uri = "https://token.actions.githubusercontent.com" }

  depends_on = [google_project_service.required]
}

resource "google_service_account_iam_member" "github_federation" {
  for_each           = local.identities
  service_account_id = google_service_account.automation[each.key].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.automation/${each.key}"

  depends_on = [google_project_service.required]
}

resource "google_storage_bucket_iam_member" "infra_state" {
  bucket = google_storage_bucket.terraform_state.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.automation["infra"].email}"

  depends_on = [google_project_service.required]
}

resource "google_project_iam_member" "automation_roles" {
  for_each = local.automation_role_bindings
  project  = var.project_id
  role     = each.value.role
  member   = "serviceAccount:${google_service_account.automation[each.value.identity].email}"

  depends_on = [google_project_service.required]
}

resource "google_storage_bucket_iam_member" "deploy_state" {
  bucket = google_storage_bucket.terraform_state.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.automation["deploy"].email}"

  depends_on = [google_project_service.required]
}
