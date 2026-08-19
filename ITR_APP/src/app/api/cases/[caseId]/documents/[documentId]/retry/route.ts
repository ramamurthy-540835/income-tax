import {Firestore,Timestamp} from "@google-cloud/firestore";
import {Storage} from "@google-cloud/storage";
import {NextRequest,NextResponse} from "next/server";
import {uuidv7} from "uuidv7";
import {requireAuthenticatedUser} from "@/lib/auth/server";
import {apiError} from "@/lib/api/errors";
import {requestId,requireSameOrigin} from "@/lib/api/request";
import {requireCloudConfiguration} from "@/lib/env";

export const runtime="nodejs";

export async function POST(request:NextRequest,{params}:{params:Promise<{caseId:string;documentId:string}>}){
 const id=requestId(request);
 try{
  requireSameOrigin(request);
  const user=await requireAuthenticatedUser(request);
  const {caseId,documentId}=await params;
  const env=requireCloudConfiguration();
  const db=new Firestore({projectId:env.GCP_PROJECT_ID,databaseId:env.FIRESTORE_DATABASE_ID});
  const caseRef=db.doc(`cases/${caseId}`);
  const [caseDoc,failedDoc]=await Promise.all([caseRef.get(),caseRef.collection("documents").doc(documentId).get()]);
  if(!caseDoc.exists||caseDoc.get("owner_uid")!==user.uid||!failedDoc.exists)throw Object.assign(new Error("Document not found"),{status:404});
  if(!["FAILED","REJECTED","REVIEW_REQUIRED"].includes(String(failedDoc.get("processingStatus"))))throw Object.assign(new Error("Only documents that need attention can be retried."),{status:409});
  const originalObject=failedDoc.get("originalObject");
  if(typeof originalObject!=="string")throw Object.assign(new Error("The immutable original is unavailable."),{status:409});
  const retryDocumentId=uuidv7();
  const retryObject=`users/${user.uid}/incoming/${caseId}/${retryDocumentId}/original`;
  const now=Timestamp.now();
  await caseRef.collection("documents").doc(retryDocumentId).create({
   documentId:retryDocumentId,clientId:caseDoc.get("clientId"),caseId,
   assessmentYear:failedDoc.get("assessmentYear")??caseDoc.get("assessmentYear")??"AY2026-27",
   originalObject:retryObject,processedObject:null,originalFilename:failedDoc.get("originalFilename")??"document",
   declaredSize:failedDoc.get("declaredSize")??null,declaredMimeType:failedDoc.get("declaredMimeType")??null,
   renamedFilename:null,documentType:null,issuer:null,documentDate:null,checksumSha256:null,
   processingStatus:"AWAITING_UPLOAD",confidence:null,evidenceStatus:"UNASSESSED",gcsGeneration:"PENDING",
   processingVersion:"doc-agent-1.0.0",createdAt:now,processedAt:null,owner_uid:user.uid,ownerUid:user.uid,
   retryOfDocumentId:documentId
  });
  const bucket=new Storage({projectId:env.GCP_PROJECT_ID}).bucket(env.GCS_QUARANTINE_BUCKET);
  try{
   await bucket.file(originalObject).copy(bucket.file(retryObject),{preconditionOpts:{ifGenerationMatch:0}});
  }catch(error){
   await caseRef.collection("documents").doc(retryDocumentId).delete();
   throw error;
  }
  return NextResponse.json({documentId:retryDocumentId,status:"AWAITING_UPLOAD"},{status:202});
 }catch(error){return apiError(error,id)}
}
