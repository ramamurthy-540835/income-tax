import type { TaxpayerIdentity } from "../shared/types.js";
export interface PasswordConvention{conventionId:string;supportedFrom?:string;supportedUntil?:string;resolver:(identity:TaxpayerIdentity)=>string}
export const verifiedConventions:readonly PasswordConvention[]=[];
export function resolveAisPassword(input:{pan:string;dateOfBirth:string;documentMetadata:{documentDate?:string|null};tryPassword:(candidate:string)=>boolean}):{password:string;conventionId:string}|null{for(const c of verifiedConventions){const password=c.resolver({normalizedPan:input.pan,dateOfBirth:input.dateOfBirth});if(input.tryPassword(password))return {password,conventionId:c.conventionId};}return null;}
