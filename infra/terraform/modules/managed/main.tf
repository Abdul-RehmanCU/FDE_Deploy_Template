locals {
  prefix = "fde-${var.customer}-prod"
  labels = merge(var.labels, {
    application = "fde-template"
    customer    = var.customer
    environment = var.environment
    profile     = "managed"
    managed-by  = "terraform"
    live-tested = "false"
  })
}

resource "google_compute_network" "managed" {
  project                 = var.project_id
  name                    = local.prefix
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

resource "google_compute_firewall" "internal" {
  project = var.project_id
  name    = "${local.prefix}-internal"
  network = google_compute_network.managed.name

  direction     = "INGRESS"
  source_ranges = ["10.64.0.0/20", "10.68.0.0/20", "10.72.0.0/16"]
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

resource "google_compute_subnetwork" "managed" {
  project                  = var.project_id
  name                     = "${local.prefix}-${var.region}"
  region                   = var.region
  network                  = google_compute_network.managed.id
  ip_cidr_range            = "10.64.0.0/20"
  private_ip_google_access = true
  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.72.0.0/16"
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.68.0.0/20"
  }
}

resource "google_compute_router" "managed" {
  project = var.project_id
  name    = local.prefix
  region  = var.region
  network = google_compute_network.managed.id
}

resource "google_compute_router_nat" "managed" {
  project                            = var.project_id
  name                               = local.prefix
  router                             = google_compute_router.managed.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"
  subnetwork {
    name                    = google_compute_subnetwork.managed.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }
  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

resource "google_compute_global_address" "private_services" {
  project       = var.project_id
  name          = "${local.prefix}-services"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.managed.id
}

resource "google_service_networking_connection" "private_services" {
  network                 = google_compute_network.managed.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services.name]
}

resource "google_service_account" "nodes" {
  project      = var.project_id
  account_id   = substr("${local.prefix}-node", 0, 30)
  display_name = "FDE managed GKE nodes"
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
  member  = "serviceAccount:${google_service_account.nodes.email}"
}

resource "google_service_account_iam_member" "infra_can_use_nodes" {
  service_account_id = google_service_account.nodes.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:fde-infra@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_container_cluster" "managed" {
  #checkov:skip=CKV_GCP_65: The reusable profile cannot invent a customer's Google Workspace security group; cluster and chart RBAC remain explicit prerequisites.
  #checkov:skip=CKV_GCP_21: resource_labels is the current provider field and is populated from mandatory installation labels; this check expects the legacy field.
  #checkov:skip=CKV_GCP_69: The separately managed node pool sets workload_metadata_config mode GKE_METADATA; this check does not follow that resource relationship.
  #checkov:skip=CKV_GCP_66: Image attestors and signing authority are customer prerequisites; silently enforcing an absent project policy could block every workload.
  project                  = var.project_id
  name                     = var.cluster_name
  location                 = var.region
  network                  = google_compute_network.managed.id
  subnetwork               = google_compute_subnetwork.managed.id
  remove_default_node_pool = true
  initial_node_count       = 1
  node_config {
    machine_type    = "e2-standard-2"
    disk_type       = "pd-balanced"
    disk_size_gb    = 50
    image_type      = "COS_CONTAINERD"
    service_account = google_service_account.nodes.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    shielded_instance_config {
      enable_integrity_monitoring = true
      enable_secure_boot          = true
    }
  }
  deletion_protection         = true
  resource_labels             = local.labels
  networking_mode             = "VPC_NATIVE"
  enable_shielded_nodes       = true
  enable_intranode_visibility = true

  release_channel { channel = "REGULAR" }
  workload_identity_config { workload_pool = "${var.project_id}.svc.id.goog" }
  master_auth {
    client_certificate_config { issue_client_certificate = false }
  }
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
    master_global_access_config { enabled = false }
  }
  master_authorized_networks_config {}
  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }
  addons_config {
    network_policy_config { disabled = false }
    http_load_balancing { disabled = false }
    gce_persistent_disk_csi_driver_config { enabled = true }
  }
  secret_manager_config { enabled = true }
  network_policy {
    enabled  = true
    provider = "CALICO"
  }
  logging_config { enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS", "APISERVER"] }
  monitoring_config { enable_components = ["SYSTEM_COMPONENTS", "APISERVER", "SCHEDULER", "CONTROLLER_MANAGER"] }
  depends_on = [google_compute_router_nat.managed, google_project_iam_member.node_roles, google_service_account_iam_member.infra_can_use_nodes]
}

resource "google_container_node_pool" "managed" {
  project    = var.project_id
  name       = "primary"
  location   = var.region
  cluster    = google_container_cluster.managed.name
  node_count = 1
  management {
    auto_repair  = true
    auto_upgrade = true
  }
  node_config {
    machine_type    = "e2-standard-2"
    disk_type       = "pd-balanced"
    disk_size_gb    = 50
    image_type      = "COS_CONTAINERD"
    service_account = google_service_account.nodes.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    metadata        = { disable-legacy-endpoints = "true" }
    workload_metadata_config { mode = "GKE_METADATA" }
    shielded_instance_config {
      enable_integrity_monitoring = true
      enable_secure_boot          = true
    }
  }
  depends_on = [google_service_account_iam_member.infra_can_use_nodes]
}

resource "google_sql_database_instance" "postgres" {
  #checkov:skip=CKV_GCP_79: PostgreSQL 16 matches the tested backup/restore and application support matrix; automatic major-version drift is unsafe.
  #checkov:skip=CKV_GCP_109: Error-statement logging is set to PANIC because ERROR can record customer SQL and plaintext parameters; operational errors remain available without query text.
  #checkov:skip=CKV_GCP_111: Logging every SQL statement can expose customer PII; pgAudit is restricted to masked DDL and role changes instead.
  project             = var.project_id
  name                = "${local.prefix}-postgres"
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = true
  settings {
    tier              = "db-custom-2-7680"
    availability_type = "REGIONAL"
    disk_type         = "PD_SSD"
    disk_size         = 20
    disk_autoresize   = true
    user_labels       = local.labels
    database_flags {
      name  = "cloudsql.enable_pgaudit"
      value = "on"
    }
    database_flags {
      name  = "pgaudit.log"
      value = "ddl,role"
    }
    database_flags {
      name  = "cloudsql.pgaudit_mask_literals"
      value = "on"
    }
    database_flags {
      name  = "pgaudit.log_parameter"
      value = "off"
    }
    database_flags {
      name  = "log_checkpoints"
      value = "on"
    }
    database_flags {
      name  = "log_connections"
      value = "on"
    }
    database_flags {
      name  = "log_disconnections"
      value = "on"
    }
    database_flags {
      name  = "log_duration"
      value = "on"
    }
    database_flags {
      name  = "log_hostname"
      value = "on"
    }
    database_flags {
      name  = "log_lock_waits"
      value = "on"
    }
    database_flags {
      name  = "log_min_messages"
      value = "error"
    }
    database_flags {
      name  = "log_min_error_statement"
      value = "panic"
    }
    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7
      backup_retention_settings {
        retained_backups = 14
        retention_unit   = "COUNT"
      }
    }
    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = google_compute_network.managed.id
      enable_private_path_for_google_cloud_services = true
      ssl_mode                                      = "TRUSTED_CLIENT_CERTIFICATE_REQUIRED"
    }
    maintenance_window {
      day          = 7
      hour         = 8
      update_track = "stable"
    }
  }
  depends_on = [google_service_networking_connection.private_services]
}

resource "google_redis_instance" "redis" {
  project                 = var.project_id
  name                    = "${local.prefix}-redis"
  region                  = var.region
  tier                    = "STANDARD_HA"
  memory_size_gb          = 5
  redis_version           = "REDIS_7_2"
  authorized_network      = google_compute_network.managed.id
  connect_mode            = "PRIVATE_SERVICE_ACCESS"
  transit_encryption_mode = "SERVER_AUTHENTICATION"
  auth_enabled            = true
  labels                  = local.labels
  maintenance_policy {
    weekly_maintenance_window {
      day = "SUNDAY"
      start_time {
        hours = 8
      }
    }
  }
  lifecycle {
    postcondition {
      condition     = self.port == 6378
      error_message = "Managed Memorystore TLS must expose the CA-verified port 6378 expected by Helm and REDIS_URL."
    }
  }
  depends_on = [google_service_networking_connection.private_services]
}

resource "google_storage_bucket" "application" {
  #checkov:skip=CKV_GCP_62: Customer project Data Access audit logging and its external log sink are explicit managed-profile prerequisites; this module does not invent that destination.
  project                     = var.project_id
  name                        = "${var.project_id}-${local.prefix}-application"
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = local.labels
  versioning { enabled = true }
  retention_policy {
    retention_period = 604800
    is_locked        = false
  }
  lifecycle_rule {
    condition {
      age                = 30
      num_newer_versions = 3
    }
    action { type = "Delete" }
  }
}

resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = substr("${local.prefix}-runtime", 0, 30)
  display_name = "FDE managed production runtime"
}

resource "google_service_account_iam_member" "infra_can_use_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:fde-infra@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_service_account_iam_member" "gke_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[production/fde-runtime]"
  depends_on         = [google_container_node_pool.managed]
}

resource "google_storage_bucket_iam_member" "runtime_objects" {
  bucket = google_storage_bucket.application.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_secret_manager_secret" "runtime" {
  for_each = toset([
    "database-ssl-cert",
    "database-ssl-key",
    "database-ssl-root-cert",
    "database-url",
    "redis-ca",
    "redis-url",
    "secret-key",
  ])
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
  for_each  = google_secret_manager_secret.runtime
  project   = var.project_id
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"

  # The chart links the production KSA to this IAM service account.
  depends_on = [google_container_node_pool.managed]
}
