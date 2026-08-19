import { NextResponse } from "next/server";
import { requireFirebaseClientConfiguration } from "@/lib/env";
export const dynamic = "force-dynamic";
export function GET(){try{return NextResponse.json(requireFirebaseClientConfiguration(),{headers:{"Cache-Control":"private, no-store"}})}catch{return NextResponse.json({error:"Authentication is unavailable."},{status:503})}}
