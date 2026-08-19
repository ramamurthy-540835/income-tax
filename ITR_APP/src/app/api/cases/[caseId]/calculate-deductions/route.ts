import {createHash} from "node:crypto";
import {Firestore,Timestamp} from "@google-cloud/firestore";
import {NextRequest,NextResponse} from "next/server";
import {uuidv7} from "uuidv7";
import {requireAuthenticatedUser} from "@/lib/auth/server";
import {apiError} from "@/lib/api/errors";
import {requestId,requireSameOrigin} from "@/lib/api/request";
import {requireCloudConfiguration} from "@/lib/env";
import {ageBandFromDob,consolidateIncomeEvidence,type IncomeEvidenceDocument} from "@/lib/tax/income-evidence";
import {analyseDeductionEvidence,type DeductionEvidenceDocument} from "@/lib/tax/deduction-evidence";
import {calculateTax} from "@/lib/tax/calculator";

const stringify=(_key:string,value:unknown)=>typeof value==="bigint"?value.toString():value;
const findingId=(documentId:string,section:string)=>createHash("sha256").update(`${documentId}:${section}`).digest("hex").slice(0,32);
export const runtime="nodejs";

export async function POST(request:NextRequest,{params}:{params:Promise<{caseId:string}>}){
 const id=requestId(request);
 try{
  requireSameOrigin(request);
  const user=await requireAuthenticatedUser(request);
  const {caseId}=await params;
  const env=requireCloudConfiguration();
  const db=new Firestore({projectId:env.GCP_PROJECT_ID,databaseId:env.FIRESTORE_DATABASE_ID});
  const caseRef=db.doc(`cases/${caseId}`);
  const caseDoc=await caseRef.get();
  if(!caseDoc.exists||caseDoc.get("owner_uid")!==user.uid)throw Object.assign(new Error("Case not found"),{status:404});
  const snapshots=await caseRef.collection("documents").where("processingStatus","==","READY").get();
  const incomeDocs:IncomeEvidenceDocument[]=[];const deductionDocs:DeductionEvidenceDocument[]=[];
  for(const document of snapshots.docs){
   const type=String(document.get("documentType"));
   const extractions=await document.ref.collection("extractions").orderBy("createdAt","desc").limit(1).get();
   const fields=extractions.docs[0]?.get("fields");
   const item={documentId:document.id,documentType:type,fields:Array.isArray(fields)?fields:[]};
   if(["FORM_16","FORM_16_PART_A","FORM_16_PART_B","SALARY_SLIP"].includes(type))incomeDocs.push({...item,documentType:type as IncomeEvidenceDocument["documentType"],issuer:document.get("issuer")??null});
   else deductionDocs.push(item);
  }
  const income=consolidateIncomeEvidence(incomeDocs);
  if(!deductionDocs.length)throw Object.assign(new Error("No ready deduction evidence is available."),{status:409});
  const identity=await db.doc(`clients/${caseDoc.get("clientId")}/private/identity`).get();
  if(!identity.exists)throw Object.assign(new Error("Date of birth is required."),{status:409});
  const ageBand=ageBandFromDob(String(identity.get("dateOfBirth")));
  const analysis=analyseDeductionEvidence(deductionDocs,ageBand);
  const zero={section80CGroup:0n,section80CCD1B:0n,section80D:0n,section80E:0n,section80TTA:0n,section80TTB:0n,section80G:0n};
  const base={grossIncomeRupees:income.adjustedSalaryRupees,salaryIncomeRupees:income.adjustedSalaryRupees,tdsRupees:income.tdsRupees,ageBand};
  const currentOld=calculateTax({...base,deductions:zero},"OLD");
  const optimizedOld=calculateTax({...base,deductions:analysis.deductions},"OLD");
  const newRegime=calculateTax({...base,grossIncomeRupees:income.grossSalaryRupees,salaryIncomeRupees:income.grossSalaryRupees,deductions:zero},"NEW");
  const estimatedTaxSavingRupees=currentOld.totalTaxRupees>optimizedOld.totalTaxRupees?currentOld.totalTaxRupees-optimizedOld.totalTaxRupees:0n;
  const createdAt=Timestamp.now();const batch=db.batch();
  for(const finding of analysis.findings){
   const ref=caseRef.collection("deductions").doc(findingId(finding.documentId,finding.section));
   batch.set(ref,{...finding,submittedRupees:finding.submittedRupees.toString(),eligibleRupees:finding.eligibleRupees.toString(),excludedRupees:finding.excludedRupees.toString(),calculationMode:"PLANNING_CANDIDATE",updatedAt:createdAt,updatedBy:user.uid},{merge:true});
  }
  const calculationId=uuidv7();
  batch.create(caseRef.collection("calculations").doc(calculationId),{calculation_id:calculationId,case_id:caseId,assessment_year:caseDoc.get("assessmentYear")??"AY2026-27",calculation_version:"deductions-v2",rules_version:optimizedOld.ruleVersion,current_old_tax:currentOld.totalTaxRupees.toString(),optimized_old_tax:optimizedOld.totalTaxRupees.toString(),new_regime_tax:newRegime.totalTaxRupees.toString(),candidate_deductions:analysis.eligibleTotalRupees.toString(),estimated_tax_saving:estimatedTaxSavingRupees.toString(),estimated_balance_after_deductions:optimizedOld.estimatedBalanceRupees.toString(),evidence_document_ids:analysis.findings.map(finding=>finding.documentId),created_at:createdAt,created_by:user.uid});
  batch.set(caseRef,{status:analysis.reviewRequired?"EVIDENCE_REVIEW":"DEDUCTIONS_CALCULATED",latestCalculationId:calculationId,updatedAt:createdAt},{merge:true});
  await batch.commit();
  return new NextResponse(JSON.stringify({calculationId,analysis,currentOld,optimizedOld,newRegime,estimatedTaxSavingRupees,notice:"Potentially eligible evidence is shown as a planning estimate until deterministic fact checks and human review verify it."},stringify),{headers:{"content-type":"application/json","cache-control":"no-store"}});
 }catch(error){return apiError(error,id)}
}
