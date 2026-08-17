import { NextRequest,NextResponse } from "next/server";
import { z } from "zod";
import { requireAuthenticatedUser } from "@/lib/auth/server";
import { apiError } from "@/lib/api/errors";
import { requestId,requireSameOrigin } from "@/lib/api/request";
import { calculateTax } from "@/lib/tax/calculator";
const money=z.union([z.string().regex(/^[0-9]+$/),z.number().int().nonnegative()]).transform(v=>BigInt(v));
const schema=z.object({grossIncomeRupees:money,salaryIncomeRupees:money,tdsRupees:money,ageBand:z.enum(["BELOW_60","SENIOR_60_TO_79","SUPER_SENIOR_80_PLUS"]),deductions:z.object({section80CGroup:money,section80CCD1B:money,section80D:money,section80TTA:money,section80TTB:money,section80G:money})});
const jsonBigInt=(_key:string,value:unknown)=>typeof value==="bigint"?value.toString():value;
export async function POST(request:NextRequest,{params}:{params:Promise<{caseId:string}>}){const id=requestId(request);try{requireSameOrigin(request);await requireAuthenticatedUser(request);await params;const input=schema.parse(await request.json());const oldResult=calculateTax(input,"OLD"),newResult=calculateTax(input,"NEW");return new NextResponse(JSON.stringify({oldResult,newResult},jsonBigInt),{headers:{"content-type":"application/json","cache-control":"no-store"}})}catch(error){return apiError(error,id)}}
