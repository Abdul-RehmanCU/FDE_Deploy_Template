locals {
  manifest = {
    project_id          = var.project_id
    project_number      = var.project_number
    region              = var.region
    zone                = var.zone
    expiry_id           = var.expiry_id
    expires_at          = var.expires_at
    cluster_name        = var.cluster_name
    artifact_repository = var.artifact_repository
    bucket_names        = sort(var.bucket_names)
    disk_names          = sort(var.disk_names)
    address_names       = sort(var.address_names)
  }
  manifest_json = jsonencode(local.manifest)
  manifest_sha  = sha256(local.manifest_json)
}

resource "google_service_account" "workflow" {
  project      = var.project_id
  account_id   = substr("fde-expiry-${var.expiry_id}", 0, 30)
  display_name = "FDE exact-resource expiry cleanup"
}

resource "google_project_iam_custom_role" "cleanup" {
  project     = var.project_id
  role_id     = replace(substr("fdeExpiry${title(replace(var.expiry_id, "-", ""))}", 0, 64), "_", "")
  title       = "FDE expiry ${var.expiry_id}"
  description = "Delete only resources named by the compiled expiry workflow"
  permissions = [
    "artifactregistry.repositories.delete",
    "artifactregistry.repositories.get",
    "artifactregistry.operations.get",
    "compute.addresses.delete",
    "compute.addresses.get",
    "compute.disks.delete",
    "compute.disks.get",
    "compute.regionOperations.get",
    "compute.zoneOperations.get",
    "container.clusters.delete",
    "container.clusters.get",
    "container.operations.get",
    "resourcemanager.projects.get",
    "storage.buckets.delete",
    "storage.buckets.get",
    "storage.objects.delete",
    "storage.objects.get",
    "storage.objects.list",
  ]
}

resource "google_project_iam_member" "workflow_cleanup" {
  project = var.project_id
  role    = google_project_iam_custom_role.cleanup.id
  member  = "serviceAccount:${google_service_account.workflow.email}"
}

resource "google_workflows_workflow" "cleanup" {
  project             = var.project_id
  name                = "fde-expiry-${var.expiry_id}"
  region              = var.region
  description         = "TTL cleanup compiled for one exact FDE resource manifest"
  service_account     = google_service_account.workflow.id
  deletion_protection = false
  labels = {
    application = "fde-template"
    expiry-id   = var.expiry_id
  }
  user_env_vars = {
    MANIFEST_SHA = local.manifest_sha
  }
  source_contents = templatefile("${path.module}/workflow.yaml.tftpl", {
    manifest_json = local.manifest_json
  })
  depends_on = [
    google_project_iam_member.workflow_cleanup,
    google_service_account_iam_member.infra_can_use_workflow,
  ]
}

resource "google_service_account" "scheduler" {
  project      = var.project_id
  account_id   = substr("fde-schedule-${var.expiry_id}", 0, 30)
  display_name = "Invoke FDE expiry workflow"
}

resource "google_service_account_iam_member" "infra_can_use_workflow" {
  service_account_id = google_service_account.workflow.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:fde-infra@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_service_account_iam_member" "infra_can_use_scheduler" {
  service_account_id = google_service_account.scheduler.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:fde-infra@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "scheduler_invoker" {
  project = var.project_id
  # Workflows does not support resource-name IAM conditions. This dedicated,
  # Scheduler-only identity receives the documented project-level invoker role.
  role   = "roles/workflows.invoker"
  member = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "expiry" {
  for_each = {
    primary    = var.expires_at
    recovery_1 = timeadd(var.expires_at, "10m")
    recovery_2 = timeadd(var.expires_at, "20m")
  }
  project          = var.project_id
  region           = var.region
  name             = "fde-expiry-${var.expiry_id}-${each.key}"
  description      = "Independent cleanup ${each.key} attempt for one exact FDE demo manifest"
  schedule         = formatdate("m h D M *", each.value)
  time_zone        = "Etc/UTC"
  attempt_deadline = "320s"

  retry_config {
    retry_count          = 3
    min_backoff_duration = "30s"
    max_backoff_duration = "300s"
    max_retry_duration   = "1800s"
  }

  http_target {
    http_method = "POST"
    uri         = "https://workflowexecutions.googleapis.com/v1/${google_workflows_workflow.cleanup.id}/executions"
    body = base64encode(jsonencode({
      argument = jsonencode({ mode = "cleanup", manifest_sha = local.manifest_sha })
    }))
    headers = { "Content-Type" = "application/json" }
    oauth_token {
      service_account_email = google_service_account.scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
  depends_on = [
    google_project_iam_member.scheduler_invoker,
    google_service_account_iam_member.infra_can_use_scheduler,
  ]

  lifecycle {
    precondition {
      condition = (
        timecmp(var.expires_at, timestamp()) > 0 &&
        timecmp(var.expires_at, timeadd(timestamp(), "3h40m")) <= 0
      )
      error_message = "expires_at must be future and at most 3h40m away, reserving two recovery executions before the four-hour limit."
    }
  }
}
