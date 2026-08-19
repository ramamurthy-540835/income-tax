import { BigQuery } from "@google-cloud/bigquery";
import type { EventSink } from "./repositories.js";
export class BigQueryEventSink implements EventSink {
 private readonly bq=new BigQuery();
 constructor(private readonly dataset:string){}
 async publish(type:string,payload:Record<string,unknown>){
  await this.bq.dataset(this.dataset).table("document_processing_events").insert([{
   event_id:crypto.randomUUID(),event_type:type,client_id:payload.client_id??"JOIN_BY_CASE",
   case_id:payload.case_id,document_id:payload.document_id,document_type:payload.document_type,
   processing_stage:payload.processing_stage??payload.status,status:payload.status,confidence:payload.confidence,
   processing_version:payload.processing_version,processing_duration_ms:payload.processing_duration_ms??null,
   error_code:payload.error_code??null,occurred_at:new Date().toISOString()
  }])
 }
}
