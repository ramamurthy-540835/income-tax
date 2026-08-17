output "quarantine_bucket" { value=google_storage_bucket.quarantine.name }
output "documents_bucket" { value=google_storage_bucket.documents.name }
output "exports_bucket" { value=google_storage_bucket.exports.name }
output "dataset" { value=google_bigquery_dataset.taxright.dataset_id }
output "web_service_account" { value=google_service_account.web.email }
output "worker_service_account" { value=google_service_account.worker.email }
