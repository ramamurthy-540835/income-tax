import { Firestore, FieldValue } from "@google-cloud/firestore";
import type { AISRecord, Classification, DocumentMetadata, TaxpayerIdentity } from "../shared/types.js";
import type { DocumentRepository } from "./repositories.js";
export class FirestoreDocumentRepository implements DocumentRepository {
 private readonly db=new Firestore();
 private readonly documentRefs=new Map<string,FirebaseFirestore.DocumentReference>();
 private ref(c:string,d:string){return this.db.doc(`cases/${c}/documents/${d}`)}
 async get(c:string,d:string){const ref=this.ref(c,d);this.documentRefs.set(d,ref);const s=await ref.get();return s.exists?s.data() as DocumentMetadata:null}
 async update(m:DocumentMetadata){await this.ref(m.caseId,m.documentId).set(m,{merge:true})}
 async transition(c:string,d:string,status:DocumentMetadata["processingStatus"]){await this.ref(c,d).update({processingStatus:status,updatedAt:FieldValue.serverTimestamp()})}
 async findExact(c:string,client:string,sum:string){const q=await this.db.collection(`cases/${c}/documents`).where("clientId","==",client).where("checksumSha256","==",sum).limit(1).get();return q.empty?null:q.docs[0]!.data() as DocumentMetadata}
 async nextSequence(client:string,ay:string,type:string,date:string|null){const cases=await this.db.collection("cases").where("clientId","==",client).get();let count=0;for(const item of cases.docs){const documents=await item.ref.collection("documents").get();count+=documents.docs.filter(doc=>doc.get("assessmentYear")===ay&&doc.get("documentType")===type&&(doc.get("documentDate")??null)===date).length}return count+1}
 async saveExtraction(documentId:string,c:Classification){const ref=this.documentRefs.get(documentId);if(!ref)throw new Error("Document reference unavailable");await ref.collection("extractions").doc().set({...c,createdAt:FieldValue.serverTimestamp()})}
 async saveAisRecords(records:AISRecord[]){if(!records.length)return;const batch=this.db.batch();for(const r of records)batch.set(this.db.doc(`cases/${r.caseId}/aisRecords/${r.aisRecordId}`),{...r,reportedAmountPaise:r.reportedAmountPaise?.toString()??null});await batch.commit()}
 async createReviewTask(x:{caseId:string;documentId:string;reason:string;confidence:number|null}){await this.db.collection(`cases/${x.caseId}/reviewTasks`).add({...x,status:"OPEN",createdAt:FieldValue.serverTimestamp()})}
 async isGenerationProcessed(d:string,g:string,v:string){return (await this.db.doc(`documentProcessing/${d}_${g}_${v.replace(/[^A-Za-z0-9]/g,"_")}`).get()).exists}
 async markGenerationProcessed(d:string,g:string,v:string){await this.db.doc(`documentProcessing/${d}_${g}_${v.replace(/[^A-Za-z0-9]/g,"_")}`).create({documentId:d,generation:g,processingVersion:v,processedAt:FieldValue.serverTimestamp()})}
 async getTaxpayerIdentityForProcessing(caseId:string):Promise<TaxpayerIdentity>{const c=await this.db.doc(`cases/${caseId}`).get();if(!c.exists)throw new Error("Case not found");const clientId=String(c.get("clientId"));const client=await this.db.doc(`clients/${clientId}/private/identity`).get();if(!client.exists)throw new Error("Taxpayer identity unavailable");return {normalizedPan:String(client.get("normalizedPan")),dateOfBirth:String(client.get("dateOfBirth"))}}
}
export async function getTaxpayerIdentityForProcessing(caseId:string):Promise<TaxpayerIdentity>{return new FirestoreDocumentRepository().getTaxpayerIdentityForProcessing(caseId)}
