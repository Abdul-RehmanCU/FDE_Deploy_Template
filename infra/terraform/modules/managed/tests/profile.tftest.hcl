mock_provider "google" {}

run "managed_profile_plan" {
  command = plan

  variables {
    project_id   = "example-fde-production"
    region       = "northamerica-northeast1"
    customer     = "example"
    environment  = "production"
    cluster_name = "fde-example-production"
    domain       = "directory.example.ca"
  }

  assert {
    condition     = google_container_cluster.managed.location == "northamerica-northeast1"
    error_message = "Managed GKE must be regional in Montréal."
  }
  assert {
    condition     = google_container_cluster.managed.deletion_protection
    error_message = "Managed GKE deletion protection must be enabled."
  }
  assert {
    condition     = google_container_cluster.managed.private_cluster_config[0].enable_private_nodes
    error_message = "Managed GKE nodes must be private."
  }
  assert {
    condition     = google_sql_database_instance.postgres.settings[0].availability_type == "REGIONAL" && google_sql_database_instance.postgres.deletion_protection
    error_message = "Managed PostgreSQL must be regional and deletion protected."
  }
  assert {
    condition     = google_redis_instance.redis.tier == "STANDARD_HA" && google_redis_instance.redis.transit_encryption_mode == "SERVER_AUTHENTICATION"
    error_message = "Managed Redis must be HA with transit encryption."
  }
  assert {
    condition     = google_storage_bucket.application.force_destroy == false && google_storage_bucket.application.public_access_prevention == "enforced"
    error_message = "Managed application storage must preserve data and prevent public access."
  }
  assert {
    condition     = output.implemented_not_live_tested
    error_message = "Managed profile must remain explicitly marked not live tested."
  }
}

run "managed_rejects_demo_environment" {
  command = plan

  variables {
    project_id   = "example-fde-production"
    customer     = "example"
    environment  = "production-demo"
    cluster_name = "fde-example-production"
    domain       = "directory.example.ca"
  }

  expect_failures = [var.environment]
}
