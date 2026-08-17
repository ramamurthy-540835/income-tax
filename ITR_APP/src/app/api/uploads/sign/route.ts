import { NextRequest,NextResponse } from "next/server";
import { requireAuthenticatedUser } from "@/lib/auth/server";
import { apiError } from "@/lib/api/errors";
import { uploadMetadataSchema,safeOriginalName } from "@/lib/documents/security";
import { requestId,requireSameOrigin } from "@/lib/api/request";
import { requireCloudConfiguration } from "@/lib/env";
export async function POST(request:NextRequest){const id=requestId(request);try{requireSameOrigin(request);await requireAuthenticatedUser(request);const input=uploadMetadataSchema.parse(await request.json());const env=requireCloudConfiguration();const documentId=crypto.randomUUID();const objectName=`cases/${input.caseId}/quarantine/${documentId}/${safeOriginalName(input.fileName)}`;return NextResponse.json({documentId,objectName,bucket:env.GCS_QUARANTINE_BUCKET,uploadUrl:null,status:"SIGNING_PROVIDER_NOT_CONNECTED",message:"V4 signing requires the approved staging service account."},{status:503})}catch(error){return apiError(error,id)}}
