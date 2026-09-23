locals {
  prefix = "fde-${var.customer}"
  labels = merge(var.labels, {
    application = "fde-template"
    customer    = var.customer
    profile     = "demo"
    managed-by  = "terraform"
    expiry-id   = var.expiry_id
  })
  secret_specs = merge([
    for namespace in var.namespaces : {
      for name in ["database-url", "postgres-password", "redis-password", "redis-url", "secret-key"] :
      "${namespace}-${name}" => { namespace = namespace, name = name }
    }
  ]...)
  persistent_disks = {
    "${local.prefix}-observability-loki"       = 8
    "${local.prefix}-observability-prometheus" = 8
    "${local.prefix}-observability-tempo"      = 8
    "${local.prefix}-production-demo-postgres" = 10
    "${local.prefix}-production-demo-redis"    = 5
    "${local.prefix}-staging-postgres"         = 10
    "${local.prefix}-staging-redis"            = 5
  }
}

resource "google_compute_disk" "data" {
  #checkov:skip=CKV_GCP_37: The bounded demo accepts Google-managed encryption; customer-managed keys add cost and key teardown risk.
  for_each = local.persistent_disks
  project  = var.project_id
  zone     = var.zone
  name     = each.key
  type     = "pd-standard"
  size     = each.value
  labels   = local.labels
}

resource "google_compute_network" "demo" {
  project                 = var.project_id
  name                    = "${local.prefix}-demo"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

resource "google_compute_firewall" "internal" {
  project = var.project_id
  name    = "${local.prefix}-internal"
  network = google_compute_network.demo.name

  direction     = "INGRESS"
  source_ranges = ["10.42.0.0/20", "10.44.0.0/20", "10.48.0.0/16"]
  allow { protocol = "icmp" }
  allow {
    protocol = "tcp"
    ports    = ["1-65535"]
  }
  allow {
    protocol = "udp"
    ports    = ["1-65535"]
  }
}

resource "google_compute_subnetwork" "demo" {
  project                  = var.project_id
  name                     = "${local.prefix}-demo-${var.region}"
  region                   = var.region
  network                  = google_compute_network.demo.id
  ip_cidr_range            = "10.42.0.0/20"
  private_ip_google_access = true
  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.1
    metadata             = "INCLUDE_ALL_METADATA"
  }

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.48.0.0/16"
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.44.0.0/20"
  }
}

resource "google_service_account" "gke_nodes" {
  project      = var.project_id
  account_id   = "${local.prefix}-gke-node"
  display_name = "FDE demo GKE nodes"
}

resource "google_project_iam_member" "node_roles" {
  for_each = toset([
    "roles/artifactregistry.reader",
    "roles/container.defaultNodeServiceAccount",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/stackdriver.resourceMetadata.writer",
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.gke_nodes.email}"
}

resource "google_service_account_iam_member" "infra_can_use_nodes" {
  service_account_id = google_service_account.gke_nodes.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:fde-infra@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_container_cluster" "demo" {
  #checkov:skip=CKV_GCP_20: GitHub-hosted demo runners have ephemeral addresses; the public control-plane endpoint is protected by IAM and the single-use paid-run gate.
  #checkov:skip=CKV_GCP_25: Private nodes require Cloud NAT, which is outside the bounded demo budget; the opt-in managed profile uses private nodes.
  #checkov:skip=CKV_GCP_64: Private nodes require Cloud NAT, which is outside the bounded demo budget; the opt-in managed profile uses private nodes.
  #checkov:skip=CKV_GCP_65: Google Groups RBAC requires customer Workspace group provisioning; Kubernetes RBAC remains explicit in the application chart.
  #checkov:skip=CKV_GCP_69: The separately managed node pool sets workload_metadata_config mode GKE_METADATA; this check does not follow that resource relationship.
  #checkov:skip=CKV_GCP_21: resource_labels is the current provider field and includes the mandatory expiry ownership label; this check expects the legacy field.
  #checkov:skip=CKV_GCP_66: The demo publishes digests but does not create Binary Authorization attestations; enabling enforcement without a real signing policy would be misleading and could block every image.
  project                  = var.project_id
  name                     = var.cluster_name
  location                 = var.zone
  network                  = google_compute_network.demo.id
  subnetwork               = google_compute_subnetwork.demo.id
  remove_default_node_pool = true
  initial_node_count       = 1
  enable_shielded_nodes    = true
  # GKE briefly creates the default pool even when Terraform removes it.
  # Give that transient pool the same scoped node identity as the real pool.
  node_config {
    machine_type    = var.machine_type
    disk_type       = "pd-standard"
    disk_size_gb    = var.node_disk_size_gb
    image_type      = "COS_CONTAINERD"
    service_account = google_service_account.gke_nodes.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    shielded_instance_config {
      enable_integrity_monitoring = true
      enable_secure_boot          = true
    }
  }
  deletion_protection         = false
  resource_labels             = local.labels
  networking_mode             = "VPC_NATIVE"
  enable_intranode_visibility = true

  release_channel { channel = "REGULAR" }
  workload_identity_config { workload_pool = "${var.project_id}.svc.id.goog" }
  master_auth {
    client_certificate_config { issue_client_certificate = false }
  }
  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }
  addons_config {
    network_policy_config { disabled = false }
    horizontal_pod_autoscaling { disabled = true }
    http_load_balancing { disabled = true }
    gcp_filestore_csi_driver_config { enabled = false }
  }
  secret_manager_config { enabled = true }
  network_policy {
    enabled  = true
    provider = "CALICO"
  }
  logging_config { enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS"] }
  monitoring_config { enable_components = ["SYSTEM_COMPONENTS"] }
  maintenance_policy {
    recurring_window {
      start_time = "2026-01-01T08:00:00Z"
      end_time   = "2026-01-01T12:00:00Z"
      recurrence = "FREQ=WEEKLY;BYDAY=SU"
    }
  }
  lifecycle {
    precondition {
      condition     = var.machine_type == "e2-standard-4"
      error_message = "Refusing a demo cluster larger or different than the approved machine."
    }
  }
  depends_on = [google_compute_disk.data, google_project_iam_member.node_roles, google_service_account_iam_member.infra_can_use_nodes]
}

resource "google_container_node_pool" "demo" {
  project    = var.project_id
  name       = "fixed-demo"
  location   = var.zone
  cluster    = google_container_cluster.demo.name
  node_count = 1

  management {
    auto_repair  = true
    auto_upgrade = true
  }
  node_config {
    machine_type    = var.machine_type
    disk_type       = "pd-standard"
    disk_size_gb    = var.node_disk_size_gb
    image_type      = "COS_CONTAINERD"
    service_account = google_service_account.gke_nodes.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    labels          = local.labels
    metadata        = { disable-legacy-endpoints = "true" }
    workload_metadata_config { mode = "GKE_METADATA" }
    shielded_instance_config {
      enable_integrity_monitoring = true
      enable_secure_boot          = true
    }
  }
  lifecycle {
    precondition {
      condition     = var.node_disk_size_gb <= 30
      error_message = "Refusing an oversized demo boot disk."
    }
  }
  depends_on = [google_service_account_iam_member.infra_can_use_nodes]
}

resource "google_artifact_registry_repository" "images" {
  #checkov:skip=CKV_GCP_84: The bounded demo accepts Google-managed encryption; customer-managed keys add cost and independent key cleanup risk.
  project                = var.project_id
  location               = var.region
  repository_id          = "${local.prefix}-images"
  format                 = "DOCKER"
  description            = "Immutable FDE deployment images"
  labels                 = local.labels
  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "delete-untagged"
    action = "DELETE"
    condition { tag_state = "UNTAGGED" }
  }
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions { keep_count = 5 }
  }
}

resource "google_storage_bucket" "application" {
  #checkov:skip=CKV_GCP_62: The bounded demo accepts no separate access-log bucket; application audit evidence and exact object-generation cleanup remain mandatory.
  for_each                    = var.namespaces
  project                     = var.project_id
  name                        = "${var.project_id}-${local.prefix}-${each.key}"
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true
  labels                      = merge(local.labels, { environment = each.key })
  versioning { enabled = true }
  soft_delete_policy { retention_duration_seconds = 0 }
  lifecycle_rule {
    condition { age = 7 }
    action { type = "Delete" }
  }
}

resource "google_service_account" "runtime" {
  for_each     = var.namespaces
  project      = var.project_id
  account_id   = substr("${local.prefix}-${each.key}", 0, 30)
  display_name = "FDE ${each.key} runtime"
}

resource "google_storage_bucket_iam_member" "runtime_objects" {
  for_each = var.namespaces
  bucket   = google_storage_bucket.application[each.key].name
  role     = "roles/storage.objectAdmin"
  member   = "serviceAccount:${google_service_account.runtime[each.key].email}"
}

resource "google_service_account_iam_member" "gke_runtime" {
  for_each           = var.namespaces
  service_account_id = google_service_account.runtime[each.key].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${each.key}/fde-runtime]"
  depends_on         = [google_container_node_pool.demo]
}

resource "google_service_account_iam_member" "infra_can_use_runtime" {
  for_each           = var.namespaces
  service_account_id = google_service_account.runtime[each.key].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:fde-infra@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_secret_manager_secret" "runtime" {
  for_each  = local.secret_specs
  project   = var.project_id
  secret_id = "${local.prefix}-${each.key}"
  labels    = local.labels
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
}

resource "google_secret_manager_secret_iam_member" "runtime" {
  for_each  = local.secret_specs
  project   = var.project_id
  secret_id = google_secret_manager_secret.runtime[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime[each.value.namespace].email}"

  # The chart links each KSA to this IAM service account for API access.
  depends_on = [google_container_node_pool.demo]
}

resource "google_secret_manager_secret_iam_member" "deploy_add_versions" {
  for_each  = local.secret_specs
  project   = var.project_id
  secret_id = google_secret_manager_secret.runtime[each.key].secret_id
  role      = "roles/secretmanager.secretVersionAdder"
  member    = "serviceAccount:fde-deploy@${var.project_id}.iam.gserviceaccount.com"
}
