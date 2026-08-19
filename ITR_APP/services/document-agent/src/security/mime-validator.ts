import { DocumentAgentError } from "../shared/errors.js";
export type SupportedMime="application/pdf"|"image/jpeg"|"image/png"|"image/webp"|"text/csv"|"application/json";
const signatures:{mime:SupportedMime;test:(b:Buffer)=>boolean}[]=[
 {mime:"application/pdf",test:b=>b.subarray(0,5).toString()==="%PDF-"},
 {mime:"image/jpeg",test:b=>b[0]===0xff&&b[1]===0xd8&&b[2]===0xff},
 {mime:"image/png",test:b=>b.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))},
 {mime:"image/webp",test:b=>b.subarray(0,4).toString()==="RIFF"&&b.subarray(8,12).toString()==="WEBP"},
 {mime:"application/json",test:b=>{try{JSON.parse(b.toString("utf8"));return true}catch{return false}}},
 {mime:"text/csv",test:b=>{const s=b.subarray(0,4096).toString("utf8");return !s.includes("\0")&&s.includes(",")&&s.includes("\n")}}
];
export function detectMime(bytes:Buffer):SupportedMime{const found=signatures.find(x=>x.test(bytes));if(!found)throw new DocumentAgentError("INVALID_FILE_TYPE","File signature is not supported");return found.mime;}
