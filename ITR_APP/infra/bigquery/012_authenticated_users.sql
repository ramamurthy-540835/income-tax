CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET}.users` (
  firebase_uid STRING NOT NULL,
  firebase_uid_hash STRING NOT NULL,
  status STRING NOT NULL,
  created_at TIMESTAMP NOT NULL,
  last_signed_in_at TIMESTAMP NOT NULL
) PARTITION BY DATE(created_at) CLUSTER BY status;
