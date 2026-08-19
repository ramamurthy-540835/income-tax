export const documentTypes = [
  "FORM_16","FORM_16_PART_A","FORM_16_PART_B","SALARY_SLIP","AIS","TIS","FORM_26AS",
  "BANK_INTEREST_CERTIFICATE","BANK_STATEMENT","HOME_LOAN_CERTIFICATE","HOME_LOAN_INTEREST_CERTIFICATE",
  "HOME_LOAN_PRINCIPAL_CERTIFICATE","LIFE_INSURANCE_PREMIUM","HEALTH_INSURANCE_PREMIUM",
  "TUITION_FEE_RECEIPT","EPF","PPF","ELSS","NSC","NPS_CONTRIBUTION","RENT_RECEIPT","RENT_AGREEMENT",
  "DONATION_80G","FORM_10BE","EDUCATION_LOAN_INTEREST","MEDICAL_EXPENSE","DISABILITY_CERTIFICATE",
  "TAX_PAYMENT_CHALLAN","ITR_ACKNOWLEDGEMENT","OTHER_TAX_DOCUMENT","UNKNOWN"
] as const;
export type DocumentType = typeof documentTypes[number];

export const processingStates = ["AWAITING_UPLOAD","UPLOADED","SECURITY_CHECK","DUPLICATE_CHECK","CLASSIFYING","PASSWORD_RESOLUTION","OCR_PROCESSING","EXTRACTING","VALIDATING","MAPPING_EVIDENCE","RENAMING","RECONCILING","REVIEW_REQUIRED","READY","FAILED","DUPLICATE","REJECTED"] as const;
export type ProcessingState = typeof processingStates[number];
export type MoneyPaise = bigint;
export interface ProvenanceField { name:string; value:string|number|null; confidence:number; sourceDocumentId:string; sourcePage:number|null; sourceRegion:string|null; extractionMethod:"DETERMINISTIC"|"DOCUMENT_AI"|"VERTEX"|"STRUCTURED"; extractorName:string; extractorVersion:string; validated:boolean; reviewStatus:"DETECTED"|"REVIEW_REQUIRED"|"VERIFIED"|"REJECTED"; }
export interface Classification { documentType:DocumentType; issuer:string|null; documentDate:string|null; financialYear:string|null; assessmentYear:string|null; candidateTaxSections:string[]; confidence:number; rationaleCodes:string[]; fields:ProvenanceField[]; }
export interface DocumentMetadata { documentId:string; clientId:string; caseId:string; assessmentYear:string; originalObject:string; processedObject:string|null; originalFilename:string; renamedFilename:string|null; documentType:DocumentType|null; issuer:string|null; documentDate:string|null; checksumSha256:string|null; processingStatus:ProcessingState; confidence:number|null; evidenceStatus:"UNASSESSED"|"POTENTIALLY_ELIGIBLE"|"EVIDENCE_REQUIRED"|"REVIEW_REQUIRED"; gcsGeneration:string; processingVersion:string; createdAt:string; processedAt:string|null; duplicateOfDocumentId?:string; }
export interface PipelineEvent { eventId:string; bucket:string; objectName:string; generation:string; contentType:string|null; size:number|null; caseId:string; documentId:string; }
export interface AISRecord { aisRecordId:string; clientId:string; caseId:string; financialYear:string; assessmentYear:string; category:"SALARY"|"TDS"|"TCS"|"INTEREST"|"DIVIDEND"|"SFT"|"TAX_PAYMENT"|"REFUND"|"DEMAND"|"GST"|"OTHER"; informationCode?:string; informationDescription?:string; informationSource?:string; reportedAmountPaise?:MoneyPaise; processedAmountPaise?:MoneyPaise; acceptedAmountPaise?:MoneyPaise; sourceDocumentId:string; reviewStatus:"MATCHED"|"MISMATCH"|"REVIEW_REQUIRED"; }
export interface TaxpayerIdentity { normalizedPan:string; dateOfBirth:string; }
