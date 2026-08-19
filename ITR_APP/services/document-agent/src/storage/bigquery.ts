import { BigQuery } from "@google-cloud/bigquery";
import type { EventSink } from "./repositories.js";
export class BigQueryEventSink implements EventSink{private readonly bq=new BigQuery();constructor(private readonly dataset:string){}async publish(type:string,payload:Record<string,unknown>){await this.bq.dataset(this.dataset).table("document_processing_events").insert([{event_id:crypto.randomUUID(),event_type:type,occurred_at:new Date().toISOString(),...payload}])}}
