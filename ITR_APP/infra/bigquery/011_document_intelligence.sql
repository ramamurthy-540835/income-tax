CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET}.document_processing_events` (
  event_id STRING NOT NULL, event_type STRING NOT NULL, case_id STRING NOT NULL,
  document_id STRING NOT NULL, document_type STRING, processing_stage STRING,
  status STRING NOT NULL, confidence FLOAT64, processing_version STRING NOT NULL,
  processing_duration_ms INT64, error_code STRING, occurred_at TIMESTAMP NOT NULL
) PARTITION BY DATE(occurred_at) CLUSTER BY event_type, status;
CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET}.document_reconciliations` (
  reconciliation_id STRING NOT NULL, case_id STRING NOT NULL, source_document_id STRING NOT NULL,
  category STRING NOT NULL, ais_amount_paise NUMERIC, evidence_amount_paise NUMERIC,
  difference_paise NUMERIC, status STRING NOT NULL, created_at TIMESTAMP NOT NULL
) PARTITION BY DATE(created_at) CLUSTER BY category, status;
