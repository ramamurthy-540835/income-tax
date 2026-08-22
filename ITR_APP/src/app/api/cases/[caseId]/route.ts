import {Firestore} from "@google-cloud/firestore";
import {NextRequest,NextResponse} from "next/server";
import {apiError} from "@/lib/api/errors";
import {requestId} from "@/lib/api/request";
import {requireAuthenticatedUser} from "@/lib/auth/server";
import {requireCloudConfiguration} from "@/lib/env";

export async function GET(request:NextRequest,{params}:{params:Promise<{caseId:string}>}){
 const id=requestId(request);
 try{
  const user=await requireAuthenticatedUser(request),{caseId}=await params,env=requireCloudConfiguration();
  const db=new Firestore({projectId:env.GCP_PROJECT_ID,databaseId:env.FIRESTORE_DATABASE_ID}),caseSnapshot=await db.doc(`cases/${caseId}`).get();
  if(!caseSnapshot.exists||caseSnapshot.get("owner_uid")!==user.uid)throw Object.assign(new Error("Case not found"),{status:404});
  const caseRef=caseSnapshot.ref;
  const [clientSnapshot,documentsSnapshot,calculationsSnapshot]=await Promise.all([
   db.doc(`clients/${caseSnapshot.get("clientId")}`).get(),
   caseRef.collection("documents").get(),
   caseRef.collection("calculations").orderBy("created_at","desc").limit(20).get()
  ]);
  if(!clientSnapshot.exists||clientSnapshot.get("owner_uid")!==user.uid)throw Object.assign(new Error("Client profile not found"),{status:404});
  const calculations=calculationsSnapshot.docs;
  const firstValue=(field:string)=>calculations.find(snapshot=>snapshot.get(field)!=null)?.get(field)??null;
  const ready=documentsSnapshot.docs.filter(snapshot=>snapshot.get("processingStatus")==="READY").length;
  return NextResponse.json({
   caseId,
   assessmentYear:caseSnapshot.get("assessmentYear")??null,
   status:caseSnapshot.get("status")??null,
   personalDetails:{fullName:clientSnapshot.get("fullName"),maskedPan:clientSnapshot.get("maskedPan")},
   calculation:{grossIncomeRupees:firstValue("gross_income"),oldRegimeTaxRupees:firstValue("current_old_tax")??firstValue("tax_liability"),candidateDeductionsRupees:firstValue("candidate_deductions"),estimatedTaxAfterDeductionsRupees:firstValue("optimized_old_tax")},
   documents:{submitted:documentsSnapshot.size,ready,pending:documentsSnapshot.size-ready},
   donation80G:caseSnapshot.get("donation80G")??null,
   preference:caseSnapshot.get("preference")??null
  },{headers:{"cache-control":"no-store"}});
 }catch(error){return apiError(error,id)}
}
