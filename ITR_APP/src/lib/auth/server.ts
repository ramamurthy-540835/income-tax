import "server-only";
import { applicationDefault, cert, getApps, initializeApp } from "firebase-admin/app";
import { getAuth } from "firebase-admin/auth";
import type { NextRequest } from "next/server";
import { serverEnv } from "@/lib/env";
import { roles, type AuthenticatedUser, type Role } from "./roles";

function adminApp(){
 if(getApps().length)return getApps()[0]!;
 const env=serverEnv();
 const credential=env.FIREBASE_CLIENT_EMAIL&&env.FIREBASE_PRIVATE_KEY&&env.GCP_PROJECT_ID?cert({projectId:env.GCP_PROJECT_ID,clientEmail:env.FIREBASE_CLIENT_EMAIL,privateKey:env.FIREBASE_PRIVATE_KEY.replace(/\\n/g,"\n")}):applicationDefault();
 return initializeApp({credential,projectId:env.FIREBASE_PROJECT_ID??env.GCP_PROJECT_ID});
}
export async function requireAuthenticatedUser(request:NextRequest):Promise<AuthenticatedUser>{
 const token=request.headers.get("authorization")?.match(/^Bearer (.+)$/)?.[1];
 if(!token)throw Object.assign(new Error("Authentication required"),{status:401});
 const decoded=await getAuth(adminApp()).verifyIdToken(token,true);
 const role=typeof decoded.role==="string"&&roles.includes(decoded.role as Role)?decoded.role as Role:"CLIENT";
 return{uid:decoded.uid,role,emailVerified:Boolean(decoded.email_verified)};
}
