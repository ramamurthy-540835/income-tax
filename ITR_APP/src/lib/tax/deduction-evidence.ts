import {AY2026_27 as rules} from "./rules/AY2026_27";
import type {TaxpayerAgeBand} from "./types";

export interface DeductionEvidenceDocument{documentId:string;documentType:string;fields:{name:string;value:string|number|null;confidence:number}[]}
type Section="80C"|"80CCD1B"|"80D"|"80E"|"80TTA_TTB"|"80G";
const mappings:Record<string,{section:Section;label:string}>={LIFE_INSURANCE_PREMIUM:{section:"80C",label:"Life insurance"},TUITION_FEE_RECEIPT:{section:"80C",label:"Eligible tuition fees"},EPF:{section:"80C",label:"EPF"},PPF:{section:"80C",label:"PPF"},ELSS:{section:"80C",label:"ELSS"},NSC:{section:"80C",label:"NSC"},HOME_LOAN_PRINCIPAL_CERTIFICATE:{section:"80C",label:"Home-loan principal"},NPS_CONTRIBUTION:{section:"80CCD1B",label:"Additional NPS"},HEALTH_INSURANCE_PREMIUM:{section:"80D",label:"Health insurance"},EDUCATION_LOAN_INTEREST:{section:"80E",label:"Education-loan interest"},BANK_INTEREST_CERTIFICATE:{section:"80TTA_TTB",label:"Bank interest"},DONATION_80G:{section:"80G",label:"Donation evidence"}};
const amount=(doc:DeductionEvidenceDocument):bigint=>{const value=doc.fields.find(field=>field.name==="deduction_amount_rupees"&&field.confidence>=.75)?.value;return typeof value==="number"&&Number.isSafeInteger(value)&&value>0?BigInt(value):typeof value==="string"&&/^\d+$/.test(value)?BigInt(value):0n};
const min=(a:bigint,b:bigint)=>a<b?a:b;

export function analyseDeductionEvidence(documents:DeductionEvidenceDocument[],ageBand:TaxpayerAgeBand){
 const preliminary=documents.flatMap(document=>{const mapping=mappings[document.documentType];if(!mapping)return [];const submitted=amount(document);return [{documentId:document.documentId,documentType:document.documentType,label:mapping.label,section:mapping.section,submittedRupees:submitted,status:submitted>0n?"POTENTIALLY_ELIGIBLE":"EVIDENCE_REQUIRED" as const}]});
 const sum=(section:Section)=>preliminary.filter(finding=>finding.section===section&&finding.status==="POTENTIALLY_ELIGIBLE").reduce((total,finding)=>total+finding.submittedRupees,0n);
 const limit80D=ageBand==="BELOW_60"?rules.limits.section80DSelfFamilyNonSenior:rules.limits.section80DSelfFamilySenior;
 const sectionLimits:Record<Section,bigint|null>={"80C":rules.limits.section80CGroup,"80CCD1B":rules.limits.section80CCD1B,"80D":limit80D,"80E":null,"80TTA_TTB":ageBand==="BELOW_60"?rules.limits.section80TTA:rules.limits.section80TTB,"80G":0n};
 const used=new Map<Section,bigint>();
 const findings=preliminary.map(finding=>{
  const limit=sectionLimits[finding.section];const consumed=used.get(finding.section)??0n;
  const available=limit===null?finding.submittedRupees:(limit>consumed?limit-consumed:0n);
  const eligible=finding.status==="POTENTIALLY_ELIGIBLE"?min(finding.submittedRupees,available):0n;
  used.set(finding.section,consumed+eligible);
  const reason=finding.section==="80G"?"80G requires separate donee-category, payment-mode and evidence validation.":finding.status==="EVIDENCE_REQUIRED"?"No reliable eligible amount was extracted.":eligible<finding.submittedRupees?"Applicable statutory ceiling limits this evidence amount.":"Within the current statutory ceiling; human evidence review remains required.";
  return {...finding,eligibleRupees:eligible,excludedRupees:finding.submittedRupees-eligible,reason};
 });
 const submitted80C=sum("80C"),submitted80D=sum("80D"),submittedNps=sum("80CCD1B"),submittedInterest=sum("80TTA_TTB");
 const deductions={section80CGroup:min(submitted80C,rules.limits.section80CGroup),section80CCD1B:min(submittedNps,rules.limits.section80CCD1B),section80D:min(submitted80D,limit80D),section80E:sum("80E"),section80TTA:ageBand==="BELOW_60"?min(submittedInterest,rules.limits.section80TTA):0n,section80TTB:ageBand==="BELOW_60"?0n:min(submittedInterest,rules.limits.section80TTB),section80G:0n};
 const eligibleTotalRupees=deductions.section80CGroup+deductions.section80CCD1B+deductions.section80D+deductions.section80E+deductions.section80TTA+deductions.section80TTB;
 return {findings,deductions,eligibleTotalRupees,gaps:[{section:"80C",limitRupees:rules.limits.section80CGroup,eligibleRupees:deductions.section80CGroup,remainingRupees:rules.limits.section80CGroup-deductions.section80CGroup},{section:"80D",limitRupees:limit80D,eligibleRupees:deductions.section80D,remainingRupees:limit80D-deductions.section80D},{section:"80CCD(1B)",limitRupees:rules.limits.section80CCD1B,eligibleRupees:deductions.section80CCD1B,remainingRupees:rules.limits.section80CCD1B-deductions.section80CCD1B}],reviewRequired:findings.some(finding=>finding.status!=="POTENTIALLY_ELIGIBLE"),excluded80GReason:"80G requires separate donee-category, payment-mode and evidence validation."};
}
