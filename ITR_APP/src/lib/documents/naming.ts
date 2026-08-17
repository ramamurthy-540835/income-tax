const slug=(v:string)=>v.toUpperCase().replace(/[^A-Z0-9]+/g,"_").replace(/^_|_$/g,"").slice(0,28)||"UNKNOWN";
export function renamedDocumentName(input:{clientId:string;assessmentYear:string;documentType:string;issuer:string|null;documentDate:string|null;sequence:number;extension:string}):string{
 const short=input.clientId.replace(/-/g,"").slice(0,6).toUpperCase();const ay=input.assessmentYear.replace(/^AY/,"AY");const date=input.documentDate?.replace(/-/g,"")??"UNDATED";const ext=input.extension.toLowerCase().replace(/[^a-z0-9]/g,"");return `TRAI_${short}_${ay}_${slug(input.documentType)}_${slug(input.issuer??"UNKNOWN")}_${date}_${String(input.sequence).padStart(2,"0")}.${ext}`;
}
