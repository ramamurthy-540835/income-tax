import type { NextRequest } from "next/server";
import { randomUUID } from "node:crypto";
import { serverEnv } from "@/lib/env";
const attempts=new Map<string,{count:number;reset:number}>();
export function requestId(request:NextRequest):string{return request.headers.get("x-request-id")?.slice(0,64)??randomUUID()}
export function requireSameOrigin(request:NextRequest):void{const origin=request.headers.get("origin");if(!origin)return;const expected=new URL(serverEnv().APP_BASE_URL).origin;if(origin!==expected)throw Object.assign(new Error("Request origin is not allowed"),{status:403})}
export function rateLimit(key:string,limit=30,windowMs=60_000):void{const now=Date.now();const item=attempts.get(key);if(!item||item.reset<now){attempts.set(key,{count:1,reset:now+windowMs});return}item.count++;if(item.count>limit)throw Object.assign(new Error("Too many requests. Please wait and try again."),{status:429})}
