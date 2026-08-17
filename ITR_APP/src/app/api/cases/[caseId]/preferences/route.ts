import { NextRequest,NextResponse } from "next/server";
import { requireAuthenticatedUser } from "@/lib/auth/server";
import { apiError } from "@/lib/api/errors";
import { preferenceSchema } from "@/lib/domain/schemas";
import { requestId,requireSameOrigin } from "@/lib/api/request";
import { auditLog } from "@/lib/security/logging";
export async function POST(request:NextRequest,{params}:{params:Promise<{caseId:string}>}){const id=requestId(request);try{requireSameOrigin(request);const user=await requireAuthenticatedUser(request);const {caseId}=await params;const body=preferenceSchema.parse({...await request.json(),caseId});auditLog({event_type:"PREFERENCE_CONFIRMED",case_id:caseId,actor_id:user.uid,status:"accepted"});return NextResponse.json({preferenceId:crypto.randomUUID(),caseId,preference:body.preference,status:"CONFIRMED"},{headers:{"cache-control":"no-store"}})}catch(error){return apiError(error,id)}}
