import {randomUUID} from "node:crypto";
import {Firestore} from "@google-cloud/firestore";
import {Storage} from "@google-cloud/storage";
import {NextRequest,NextResponse} from "next/server";
import {requireAuthenticatedUser} from "@/lib/auth/server";
import {apiError} from "@/lib/api/errors";
import {requestId,requireSameOrigin} from "@/lib/api/request";
import {requireCloudConfiguration} from "@/lib/env";
import {buildStoredZip} from "@/lib/documents/zip";
export const runtime="nodejs";
export async function POST(request:NextRequest,{params}:{params:Promise<{caseId:string}>}){const id=requestId(request);try{requireSameOrigin(request);const user=await requireAuthenticatedUser(request),{caseId}=await params,env=requireCloudConfiguration(),db=new Firestore({projectId:env.GCP_PROJECT_ID,databaseId:env.FIRESTORE_DATABASE_ID}),caseDoc=await db.doc(`cases/${caseId}`).get();if(!caseDoc.exists||caseDoc.get("owner_uid")!==user.uid)throw Object.assign(new Error("Case not found"),{status:404});const docs=await db.collection(`cases/${caseId}/documents`).where("processingStatus","==","READY").get(),storage=new Storage({projectId:env.GCP_PROJECT_ID}),files:{name:string;data:Buffer}[]=[];for(const doc of docs.docs){const object=doc.get("processedObject"),name=doc.get("renamedFilename");if(typeof object!=="string"||typeof name!=="string")continue;const [data]=await storage.bucket(env.GCS_DOCUMENT_BUCKET).file(object).download();files.push({name,data})}if(!files.length)throw Object.assign(new Error("No ready renamed documents are available."),{status:409});const zip=buildStoredZip(files),archive=`exports/${caseId}/${randomUUID()}/TaxRightAI_${caseId.slice(-6).toUpperCase()}_${caseDoc.get("assessmentYear")??"AY2026-27"}_RenamedDocuments.zip`,file=storage.bucket(env.GCS_EXPORT_BUCKET).file(archive);await file.save(zip,{resumable:false,contentType:"application/zip",preconditionOpts:{ifGenerationMatch:0}});const [downloadUrl]=await file.getSignedUrl({version:"v4",action:"read",expires:Date.now()+10*60_000});return NextResponse.json({downloadUrl,expiresInSeconds:600,fileCount:files.length})}catch(error){return apiError(error,id)}}
