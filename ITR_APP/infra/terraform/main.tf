provider "google" { project=var.project_id region=var.region }
locals { prefix="taxright-${var.environment}" labels={ application="taxright-ai" environment=var.environment managed_by="terraform" } }
resource "google_storage_bucket" "quarantine" { name="${var.project_id}-${local.prefix}-quarantine" location=var.region uniform_bucket_level_access=true public_access_prevention="enforced" force_destroy=false labels=local.labels cors { origin=var.web_origins method=["PUT"] response_header=["Content-Type","ETag"] max_age_seconds=3600 } lifecycle_rule { condition { age=7 } action { type="Delete" } } }
resource "google_storage_bucket" "documents" { name="${var.project_id}-${local.prefix}-documents" location=var.region uniform_bucket_level_access=true public_access_prevention="enforced" force_destroy=false labels=local.labels versioning { enabled=true } lifecycle_rule { condition { num_newer_versions=3 } action { type="Delete" } } }
resource "google_storage_bucket" "exports" { name="${var.project_id}-${local.prefix}-exports" location=var.region uniform_bucket_level_access=true public_access_prevention="enforced" force_destroy=false labels=local.labels lifecycle_rule { condition { age=1 } action { type="Delete" } } }
resource "google_bigquery_dataset" "taxright" { dataset_id="taxright_${var.environment}" location=var.region delete_contents_on_destroy=false labels=local.labels }
resource "google_service_account" "web" { account_id="taxright-web-${var.environment}" display_name="TaxRight web ${var.environment}" }
resource "google_service_account" "document_agent" { account_id="taxright-doc-agent-${var.environment}" display_name="TaxRight Document Intelligence Agent ${var.environment}" }
resource "google_storage_bucket_iam_member" "agent_quarantine_reader" { bucket=google_storage_bucket.quarantine.name role="roles/storage.objectViewer" member="serviceAccount:${google_service_account.document_agent.email}" }
resource "google_storage_bucket_iam_member" "agent_documents_writer" { bucket=google_storage_bucket.documents.name role="roles/storage.objectCreator" member="serviceAccount:${google_service_account.document_agent.email}" }
resource "google_storage_bucket_iam_member" "agent_exports_writer" { bucket=google_storage_bucket.exports.name role="roles/storage.objectAdmin" member="serviceAccount:${google_service_account.document_agent.email}" }
resource "google_project_iam_member" "agent_document_ai" { project=var.project_id role="roles/documentai.apiUser" member="serviceAccount:${google_service_account.document_agent.email}" }
resource "google_project_iam_member" "agent_vertex" { project=var.project_id role="roles/aiplatform.user" member="serviceAccount:${google_service_account.document_agent.email}" }
resource "google_cloud_run_v2_service" "document_agent" {
  name="taxright-document-agent-${var.environment}" location=var.region deletion_protection=true
  template { service_account=google_service_account.document_agent.email timeout="900s" max_instance_request_concurrency=4 scaling { min_instance_count=0 max_instance_count=10 }
    containers { image=var.document_agent_image resources { limits={ cpu="2" memory="2Gi" } }
      env { name="APP_ENV" value=var.environment } env { name="GCP_PROJECT_ID" value=var.project_id }
      env { name="GCS_QUARANTINE_BUCKET" value=google_storage_bucket.quarantine.name } env { name="GCS_DOCUMENT_BUCKET" value=google_storage_bucket.documents.name }
      env { name="GCS_EXPORT_BUCKET" value=google_storage_bucket.exports.name } env { name="BQ_DATASET" value=google_bigquery_dataset.taxright.dataset_id }
      env { name="DOCUMENT_AI_LOCATION" value=var.region }
    }
  }
}
resource "google_eventarc_trigger" "document_uploaded" { name="taxright-document-uploaded-${var.environment}" location=var.region service_account=google_service_account.document_agent.email
  matching_criteria { attribute="type" value="google.cloud.storage.object.v1.finalized" }
  matching_criteria { attribute="bucket" value=google_storage_bucket.quarantine.name }
  destination { cloud_run_service { service=google_cloud_run_v2_service.document_agent.name region=var.region path="/events/gcs" } }
}
resource "google_secret_manager_secret" "pan_pepper" { secret_id="taxright-pan-hmac-pepper-${var.environment}" replication { user_managed { replicas { location=var.region } } } labels=local.labels }
resource "google_kms_key_ring" "taxright" { name="taxright-${var.environment}" location=var.region }
resource "google_kms_crypto_key" "pii" { name="pii-envelope" key_ring=google_kms_key_ring.taxright.id rotation_period="7776000s" lifecycle { prevent_destroy=true } }
