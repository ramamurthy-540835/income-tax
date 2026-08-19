import { z } from "zod";
export const allowedDocumentTypes=["application/pdf","image/jpeg","image/png","image/webp","text/csv","application/json"] as const;
export const uploadMetadataSchema=z.object({fileName:z.string().min(1).max(180),mimeType:z.enum(allowedDocumentTypes),size:z.number().int().positive().max(25_000_000),caseId:z.uuid(),assessmentYear:z.string().regex(/^AY20\d{2}-\d{2}$/)});
const signatures:{mime:(typeof allowedDocumentTypes)[number];bytes:number[]}[]=[{mime:"application/pdf",bytes:[0x25,0x50,0x44,0x46]},{mime:"image/jpeg",bytes:[0xff,0xd8,0xff]},{mime:"image/png",bytes:[0x89,0x50,0x4e,0x47]},{mime:"image/webp",bytes:[0x52,0x49,0x46,0x46]}];
export function signatureMatches(bytes:Uint8Array,mime:(typeof allowedDocumentTypes)[number]):boolean{if(mime==="application/json"){try{JSON.parse(new TextDecoder().decode(bytes));return true}catch{return false}}if(mime==="text/csv")return new TextDecoder().decode(bytes).includes(",");const sig=signatures.find(s=>s.mime===mime);return Boolean(sig&&sig.bytes.every((b,i)=>bytes[i]===b));}
export function safeOriginalName(name:string):string{return name.replace(/[^A-Za-z0-9._-]/g,"_").replace(/_+/g,"_").slice(0,180)}
