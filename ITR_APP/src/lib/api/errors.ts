import { NextResponse } from "next/server";
import { ZodError } from "zod";
import { auditLog } from "@/lib/security/logging";
export function apiError(error:unknown,requestId:string):NextResponse{
 const status=typeof error==="object"&&error&&"status" in error&&typeof error.status==="number"?error.status:error instanceof ZodError?400:500;
 const code=status===401?"AUTHENTICATION_REQUIRED":status===403?"FORBIDDEN":status===400?"INVALID_REQUEST":"INTERNAL_ERROR";
 auditLog({event_type:"API_ERROR",request_id:requestId,status,error_code:code});
 return NextResponse.json({error:{code,message:status===500?"We couldn’t complete that request. Please try again.":error instanceof Error?error.message:"Invalid request",requestId}},{status});
}
