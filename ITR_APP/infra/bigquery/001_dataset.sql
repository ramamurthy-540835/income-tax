-- Replace ${PROJECT_ID} and ${DATASET} through the migration runner.
CREATE SCHEMA IF NOT EXISTS `${PROJECT_ID}.${DATASET}` OPTIONS(location="asia-south1", description="TaxRight downstream analytics; Firestore remains operational source");
