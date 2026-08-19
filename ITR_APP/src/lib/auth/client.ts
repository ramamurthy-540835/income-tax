"use client";
import {getApp,getApps,initializeApp} from "firebase/app";
import {getAuth} from "firebase/auth";
const config={apiKey:process.env.NEXT_PUBLIC_FIREBASE_API_KEY,authDomain:process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,projectId:process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,appId:process.env.NEXT_PUBLIC_FIREBASE_APP_ID};
export async function currentIdToken():Promise<string>{if(!config.apiKey||!config.authDomain||!config.projectId||!config.appId)throw new Error("Firebase client authentication is not configured.");const app=getApps().length?getApp():initializeApp(config);const user=getAuth(app).currentUser;if(!user)throw new Error("Please sign in before uploading documents.");return user.getIdToken()}
