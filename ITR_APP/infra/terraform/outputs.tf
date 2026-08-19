output "quarantine_bucket" { value=google_storage_bucket.quarantine.name }
output "documents_bucket" { value=google_storage_bucket.documents.name }
output "exports_bucket" { value=google_storage_bucket.exports.name }
output "dataset" { value=google_bigquery_dataset.taxright.dataset_id }
output "web_service_account" { value=google_service_account.web.email }
output "document_agent_service_account" { value=google_service_account.document_agent.email }
output "document_agent_service" { value=google_cloud_run_v2_service.document_agent.name }
