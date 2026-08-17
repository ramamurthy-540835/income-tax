import { NextRequest,NextResponse } from "next/server";
import { requireAuthenticatedUser } from "@/lib/auth/server";
import { apiError } from "@/lib/api/errors";
import { requestId,requireSameOrigin } from "@/lib/api/request";
import { auditLog } from "@/lib/security/logging";
export async function POST(request:NextRequest,{params}:{params:Promise<{caseId:string}>}){const id=requestId(request);try{requireSameOrigin(request);const user=await requireAuthenticatedUser(request);const {caseId}=await params;auditLog({event_type:"CASE_SUBMITTED_FOR_REVIEW",case_id:caseId,actor_id:user.uid,status:"accepted"});return NextResponse.json({caseId,status:"SUBMITTED_FOR_REVIEW"},{headers:{"cache-control":"no-store"}})}catch(error){return apiError(error,id)}}
