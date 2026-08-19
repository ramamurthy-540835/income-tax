import { NextRequest,NextResponse } from "next/server";
import { Firestore,FieldValue } from "@google-cloud/firestore";
import { requireAuthenticatedUser } from "@/lib/auth/server";
import { requireSameOrigin,requestId } from "@/lib/api/request";
import { apiError } from "@/lib/api/errors";
import { requireCloudConfiguration } from "@/lib/env";
import { syncAuthenticatedUser } from "@/lib/analytics/bigquery";
export const runtime="nodejs";
export async function POST(request:NextRequest){const id=requestId(request);try{requireSameOrigin(request);const user=await requireAuthenticatedUser(request),env=requireCloudConfiguration(),now=new Date().toISOString(),db=new Firestore({projectId:env.GCP_PROJECT_ID,databaseId:env.FIRESTORE_DATABASE_ID});await db.doc(`users/${user.uid}`).set({firebase_uid:user.uid,role:user.role,status:"ACTIVE",last_signed_in_at:FieldValue.serverTimestamp(),created_at:FieldValue.serverTimestamp()},{merge:true});await syncAuthenticatedUser({projectId:env.GCP_PROJECT_ID,dataset:env.BQ_DATASET,firebaseUid:user.uid,timestamp:now});return NextResponse.json({uid:user.uid,status:"ACTIVE"},{headers:{"cache-control":"no-store"}})}catch(error){return apiError(error,id)}}
