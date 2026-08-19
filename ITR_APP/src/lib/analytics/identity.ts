import {createHash} from "node:crypto";
export const firebaseUidHash=(uid:string)=>createHash("sha256").update(uid).digest("hex");
