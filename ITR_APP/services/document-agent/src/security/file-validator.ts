import { DocumentAgentError } from "../shared/errors.js";
import { detectMime,type SupportedMime } from "./mime-validator.js";
import { inspectPdf } from "./pdf-validator.js";
export function validateFile(bytes:Buffer,declared:string|null,maxBytes:number):{mime:SupportedMime;encrypted:boolean;pages:number}{if(bytes.length>maxBytes)throw new DocumentAgentError("FILE_TOO_LARGE","File exceeds configured limit");const mime=detectMime(bytes);if(declared&&declared!==mime&&!(declared==="image/jpg"&&mime==="image/jpeg"))throw new DocumentAgentError("INVALID_FILE_TYPE","Declared MIME does not match file signature");const pdf=mime==="application/pdf"?inspectPdf(bytes):{encrypted:false,pageEstimate:1};return {mime,encrypted:pdf.encrypted,pages:pdf.pageEstimate};}
