-- Apply through an identity-aware migration job after replacing placeholders.
-- Example authorised staff view intentionally excludes pan_fingerprint.
CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.staff_case_queue` AS SELECT case_id,client_id,assessment_year,status,assigned_staff_id,created_at,updated_at FROM `${PROJECT_ID}.${DATASET}.cases`;
-- Row access policies and policy-tag assignments require approved group/service-account identities and are applied by Terraform after review.
