import { v1 as documentai } from "@google-cloud/documentai";
import { DocumentAgentError } from "../shared/errors.js";
import type { Extractor, OcrResult } from "./extractor.js";

export class DocumentAiExtractor implements Extractor {
  private readonly client:documentai.DocumentProcessorServiceClient;
  constructor(private readonly processorName:string){
    const location=/\/locations\/([^/]+)\//.exec(processorName)?.[1];
    if(!location)throw new DocumentAgentError("CONFIGURATION_ERROR","Document AI processor location is invalid");
    this.client=new documentai.DocumentProcessorServiceClient({apiEndpoint:`${location}-documentai.googleapis.com`});
  }
  async extract(bytes:Buffer,mime:string,documentId:string):Promise<OcrResult>{
    try{const [result]=await this.client.processDocument({name:this.processorName,rawDocument:{content:bytes.toString("base64"),mimeType:mime}});const doc=result.document;const blocks=doc?.pages?.flatMap(page=>page.blocks??[])??[];const confidence=blocks.reduce((sum,block)=>sum+(block.layout?.confidence??0),0)/(blocks.length||1);return {text:doc?.text??"",confidence,provider:"document-ai",fields:[]}}
    catch{throw new DocumentAgentError("DOCUMENT_AI_FAILED",`Document AI failed for document ${documentId}`,true)}
  }
}
