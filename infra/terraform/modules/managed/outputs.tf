output "implemented_not_live_tested" { value = true }
output "cluster_name" { value = google_container_cluster.managed.name }
output "postgres_private_ip" {
  value     = google_sql_database_instance.postgres.private_ip_address
  sensitive = true
}
output "redis_host" {
  value     = google_redis_instance.redis.host
  sensitive = true
}
output "application_bucket" { value = google_storage_bucket.application.name }
output "customer_domain" { value = var.domain }
