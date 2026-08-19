import { randomUUID } from "node:crypto";
import { buildZip } from "./zip-builder.js";
import type { ObjectStore } from "../storage/repositories.js";
export class ExportService{constructor(private readonly objects:ObjectStore){}async create(input:{caseId:string;caseNumber:string;assessmentYear:string;files:{folder:string;filename:string;bytes:Buffer}[]}):Promise<string>{const zip=buildZip(input.files.map(f=>({name:`${f.folder}/${f.filename}`,data:f.bytes})));const key=`exports/${input.caseId}/${randomUUID()}/TaxRightAI_${input.caseNumber}_${input.assessmentYear}_RenamedDocuments.zip`;return this.objects.writeExport(key,zip)}}
