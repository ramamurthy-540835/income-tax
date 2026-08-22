import { NextRequest,NextResponse } from "next/server";
import { requireAuthenticatedUser } from "@/lib/auth/server";
import { apiError } from "@/lib/api/errors";
import { preferenceSchema } from "@/lib/domain/schemas";
import { requestId,requireSameOrigin } from "@/lib/api/request";
import { auditLog } from "@/lib/security/logging";
import {Firestore,FieldValue} from "@google-cloud/firestore";
import {requireCloudConfiguration} from "@/lib/env";
export async function POST(request:NextRequest,{params}:{params:Promise<{caseId:string}>}){const id=requestId(request);try{requireSameOrigin(request);const user=await requireAuthenticatedUser(request);const {caseId}=await params;const body=preferenceSchema.parse({...await request.json(),caseId}),env=requireCloudConfiguration(),db=new Firestore({projectId:env.GCP_PROJECT_ID,databaseId:env.FIRESTORE_DATABASE_ID}),caseRef=db.doc(`cases/${caseId}`),snapshot=await caseRef.get();if(!snapshot.exists||snapshot.get("owner_uid")!==user.uid)throw Object.assign(new Error("Case not found"),{status:404});await caseRef.set({preference:body.preference,updatedAt:FieldValue.serverTimestamp()},{merge:true});auditLog({event_type:"PREFERENCE_CONFIRMED",case_id:caseId,actor_id:user.uid,status:"accepted"});return NextResponse.json({preferenceId:crypto.randomUUID(),caseId,preference:body.preference,status:"CONFIRMED"},{headers:{"cache-control":"no-store"}})}catch(error){return apiError(error,id)}}
