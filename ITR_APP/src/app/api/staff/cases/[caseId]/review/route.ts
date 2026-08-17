import { NextRequest,NextResponse } from "next/server";
import { z } from "zod";
import { requireAuthenticatedUser } from "@/lib/auth/server";
import { requireRole } from "@/lib/auth/roles";
import { apiError } from "@/lib/api/errors";
import { requestId,requireSameOrigin } from "@/lib/api/request";
import { auditLog } from "@/lib/security/logging";
const schema=z.object({entityType:z.enum(["EXTRACTION","DEDUCTION"]),entityId:z.uuid(),decision:z.enum(["APPROVE","REJECT","REQUEST_EVIDENCE"]),reason:z.string().trim().min(3).max(500)});
export async function POST(request:NextRequest,{params}:{params:Promise<{caseId:string}>}){const id=requestId(request);try{requireSameOrigin(request);const user=requireRole(await requireAuthenticatedUser(request),["TAX_PREPARER","AUDITOR","ADMIN"]);const {caseId}=await params;const body=schema.parse(await request.json());auditLog({event_type:"REVIEW_DECISION",case_id:caseId,actor_id:user.uid,entity_type:body.entityType,entity_id:body.entityId,status:body.decision});return NextResponse.json({caseId,status:"RECORDED"},{headers:{"cache-control":"no-store"}})}catch(error){return apiError(error,id)}}
