import { NextRequest,NextResponse } from "next/server";
import { createCaseSchema } from "@/lib/domain/schemas";
import { newCaseId,newClientId,panFingerprint } from "@/lib/domain/identity";
import { requireAuthenticatedUser } from "@/lib/auth/server";
import { apiError } from "@/lib/api/errors";
import { rateLimit,requestId,requireSameOrigin } from "@/lib/api/request";
import { auditLog } from "@/lib/security/logging";
export async function POST(request:NextRequest){const id=requestId(request);try{requireSameOrigin(request);const user=await requireAuthenticatedUser(request);rateLimit(user.uid,10);const body=createCaseSchema.parse(await request.json());const pepper=process.env.PAN_HMAC_PEPPER;if(!pepper)throw new Error("PAN fingerprint service is not configured");const clientId=newClientId(),caseId=newCaseId();const fingerprint=panFingerprint(body.profile.pan,pepper);auditLog({event_type:"CASE_CREATE_REQUESTED",case_id:caseId,actor_id:user.uid,status:"accepted"});return NextResponse.json({clientId,caseId,status:"DRAFT",panFingerprintStored:Boolean(fingerprint)},{status:201,headers:{"cache-control":"no-store"}})}catch(error){return apiError(error,id)}}
