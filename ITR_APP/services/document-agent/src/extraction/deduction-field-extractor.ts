import type {DocumentType,ProvenanceField} from "../shared/types.js";

const numeric=(raw:string|undefined):number|null=>{
 if(!raw)return null;
 const value=Number(raw.replace(/[,\s]/g,""));
 return Number.isFinite(value)&&value>0&&Number.isSafeInteger(Math.round(value))?Math.round(value):null;
};
const firstAmount=(text:string,patterns:RegExp[]):number|null=>{
 for(const pattern of patterns){const value=numeric(pattern.exec(text)?.[1]);if(value!==null)return value}
 return null;
};
const generic=(text:string)=>firstAmount(text,[/(?:premium|contribution|interest\s+paid|amount\s+paid|total\s+paid)[^\d]{0,40}(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d{1,2})?)/i]);
const make=(name:string,value:number|null,documentId:string,confidence=.92):ProvenanceField=>({name,value,confidence:value===null?0:confidence,sourceDocumentId:documentId,sourcePage:null,sourceRegion:null,extractionMethod:"DETERMINISTIC",extractorName:"deduction-field-extractor",extractorVersion:"1.1.0",validated:value!==null,reviewStatus:value===null?"REVIEW_REQUIRED":"DETECTED"});

function deductionAmount(text:string,type:DocumentType):number|null{
 switch(type){
  case "TUITION_FEE_RECEIPT":return firstAmount(text,[/(?:eligible\s+)?tuition(?:\s+fee)?[^\d]{0,50}(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d{1,2})?)/i]);
  case "HEALTH_INSURANCE_PREMIUM":case "LIFE_INSURANCE_PREMIUM":return firstAmount(text,[/(?:premium\s+(?:paid|amount)|total\s+premium|premium)[^\d]{0,50}(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d{1,2})?)/i]);
  case "NPS_CONTRIBUTION":case "EPF":case "PPF":case "ELSS":case "NSC":return firstAmount(text,[/(?:contribution|deposit|invested\s+amount|amount\s+paid)[^\d]{0,50}(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d{1,2})?)/i]);
  case "HOME_LOAN_PRINCIPAL_CERTIFICATE":return firstAmount(text,[/(?:principal\s+(?:repaid|repayment|paid)|principal\s+component)[^\d]{0,50}(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d{1,2})?)/i]);
  case "EDUCATION_LOAN_INTEREST":return firstAmount(text,[/(?:interest\s+(?:paid|component)|eligible\s+interest)[^\d]{0,50}(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d{1,2})?)/i]);
  case "BANK_INTEREST_CERTIFICATE":return firstAmount(text,[/(?:interest\s+(?:earned|credited|paid)|total\s+interest)[^\d]{0,50}(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d{1,2})?)/i]);
  case "DONATION_80G":return firstAmount(text,[/(?:donation\s+amount|amount\s+donated|amount\s+paid)[^\d]{0,50}(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d{1,2})?)/i]);
  default:return generic(text);
 }
}

export function extractDeductionFields(text:string,documentId:string,type:DocumentType):ProvenanceField[]{
 const supported:DocumentType[]=["LIFE_INSURANCE_PREMIUM","HEALTH_INSURANCE_PREMIUM","TUITION_FEE_RECEIPT","EPF","PPF","ELSS","NSC","NPS_CONTRIBUTION","BANK_INTEREST_CERTIFICATE","HOME_LOAN_PRINCIPAL_CERTIFICATE","EDUCATION_LOAN_INTEREST","DONATION_80G"];
 if(!supported.includes(type))return [];
 const fields=[make("deduction_amount_rupees",deductionAmount(text,type),documentId)];
 if(type==="TUITION_FEE_RECEIPT")fields.push(make("tuition_fee_rupees",deductionAmount(text,type),documentId));
 return fields;
}
