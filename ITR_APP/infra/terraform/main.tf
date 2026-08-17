provider "google" { project=var.project_id region=var.region }
locals { prefix="taxright-${var.environment}" labels={ application="taxright-ai" environment=var.environment managed_by="terraform" } }
resource "google_storage_bucket" "quarantine" { name="${var.project_id}-${local.prefix}-quarantine" location=var.region uniform_bucket_level_access=true public_access_prevention="enforced" force_destroy=false labels=local.labels lifecycle_rule { condition { age=7 } action { type="Delete" } } }
resource "google_storage_bucket" "documents" { name="${var.project_id}-${local.prefix}-documents" location=var.region uniform_bucket_level_access=true public_access_prevention="enforced" force_destroy=false labels=local.labels versioning { enabled=true } lifecycle_rule { condition { num_newer_versions=3 } action { type="Delete" } } }
resource "google_storage_bucket" "exports" { name="${var.project_id}-${local.prefix}-exports" location=var.region uniform_bucket_level_access=true public_access_prevention="enforced" force_destroy=false labels=local.labels lifecycle_rule { condition { age=1 } action { type="Delete" } } }
resource "google_bigquery_dataset" "taxright" { dataset_id="taxright_${var.environment}" location=var.region delete_contents_on_destroy=false labels=local.labels }
resource "google_service_account" "web" { account_id="taxright-web-${var.environment}" display_name="TaxRight web ${var.environment}" }
resource "google_service_account" "worker" { account_id="taxright-worker-${var.environment}" display_name="TaxRight document worker ${var.environment}" }
resource "google_secret_manager_secret" "pan_pepper" { secret_id="taxright-pan-hmac-pepper-${var.environment}" replication { user_managed { replicas { location=var.region } } } labels=local.labels }
resource "google_kms_key_ring" "taxright" { name="taxright-${var.environment}" location=var.region }
resource "google_kms_crypto_key" "pii" { name="pii-envelope" key_ring=google_kms_key_ring.taxright.id rotation_period="7776000s" lifecycle { prevent_destroy=true } }
