"use client";
import { getApp, getApps, initializeApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";
type PublicFirebaseConfig = { apiKey:string; authDomain:string; projectId:string; appId:string };
let authPromise:Promise<Auth>|undefined;
export function firebaseAuth():Promise<Auth>{
  authPromise??=fetch("/api/config/firebase",{cache:"no-store"}).then(async response=>{
    if(!response.ok)throw new Error("Sign-in is not configured for this environment.");
    return response.json() as Promise<PublicFirebaseConfig>;
  }).then(config=>getAuth(getApps().length?getApp():initializeApp(config)));
  return authPromise;
}
export async function currentIdToken():Promise<string>{const user=(await firebaseAuth()).currentUser;if(!user)throw new Error("Please sign in before continuing.");return user.getIdToken()}
