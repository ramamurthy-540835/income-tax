import { NextRequest,NextResponse } from "next/server";
import { z } from "zod";
import { requireAuthenticatedUser } from "@/lib/auth/server";
import { apiError } from "@/lib/api/errors";
import { requestId,requireSameOrigin } from "@/lib/api/request";
import { calculate80G } from "@/lib/tax/80g";
const schema=z.object({donatedRupees:z.string().regex(/^[0-9]+$/).transform(BigInt),adjustedGrossTotalIncomeRupees:z.string().regex(/^[0-9]+$/).transform(BigInt),category:z.enum(["FULL_NO_LIMIT","HALF_NO_LIMIT","FULL_QUALIFYING_LIMIT","HALF_QUALIFYING_LIMIT"]),mode:z.enum(["CASH","NON_CASH"]),evidenceVerified:z.literal(false)});
export async function POST(request:NextRequest,{params}:{params:Promise<{caseId:string}>}){const id=requestId(request);try{requireSameOrigin(request);await requireAuthenticatedUser(request);await params;const result=calculate80G(schema.parse(await request.json()));return NextResponse.json({...result,qualifyingContributionRupees:result.qualifyingContributionRupees.toString(),eligibleDeductionRupees:result.eligibleDeductionRupees.toString()},{headers:{"cache-control":"no-store"}})}catch(error){return apiError(error,id)}}
