import type { Classification,ProvenanceField } from "../shared/types.js";
export interface OcrResult{text:string;fields:ProvenanceField[];confidence:number;provider:string}
export interface Extractor{extract(bytes:Buffer,mime:string,documentId:string):Promise<OcrResult>}
export class LocalTextExtractor implements Extractor{async extract(bytes:Buffer,mime:string):Promise<OcrResult>{if(mime!=="application/json"&&mime!=="text/csv"&&mime!=="application/pdf")return {text:"",fields:[],confidence:0,provider:"local"};const text=bytes.toString(mime==="application/pdf"?"latin1":"utf8");return {text,fields:[],confidence:mime==="application/pdf"?.45:1,provider:"local"};}}
export function mergeExtraction(classification:Classification,ocr:OcrResult):Classification{return {...classification,fields:[...classification.fields,...ocr.fields],confidence:Math.max(classification.confidence,Math.min(1,(classification.confidence*.7)+(ocr.confidence*.3)))};}
