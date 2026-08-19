import type { DocumentType } from "../shared/types.js";
const map:Partial<Record<DocumentType,string[]>>={LIFE_INSURANCE_PREMIUM:["80C"],TUITION_FEE_RECEIPT:["80C"],PPF:["80C"],EPF:["80C"],ELSS:["80C"],NSC:["80C"],HEALTH_INSURANCE_PREMIUM:["80D"],NPS_CONTRIBUTION:["80CCD","80CCD(1B)"],DONATION_80G:["80G"],EDUCATION_LOAN_INTEREST:["80E"]};
export const mapTaxEvidence=(type:DocumentType):{candidateSections:string[];status:"UNASSESSED"|"POTENTIALLY_ELIGIBLE"}=>{const candidateSections=map[type]??[];return {candidateSections,status:candidateSections.length?"POTENTIALLY_ELIGIBLE":"UNASSESSED"};};
