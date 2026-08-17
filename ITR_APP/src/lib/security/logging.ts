const sensitiveKey=/pan|aadhaar|mobile|phone|email|account|policy|signed.?url|ocr|document.?text/i;
export function redactForLog(value:unknown):unknown{
 if(Array.isArray(value))return value.map(redactForLog);
 if(value&&typeof value==="object")return Object.fromEntries(Object.entries(value as Record<string,unknown>).map(([k,v])=>[k,sensitiveKey.test(k)?"[REDACTED]":redactForLog(v)]));
 return value;
}
export function auditLog(event:Record<string,unknown>):void{console.info(JSON.stringify(redactForLog(event)));}
