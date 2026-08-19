const forbidden=/pan|dob|birth|aadhaar|mobile|email|password|otp|signed.?url|ocr|policy|account/i;
export function log(level:"info"|"warn"|"error",event:Record<string,unknown>):void{const safe=Object.fromEntries(Object.entries(event).filter(([k])=>!forbidden.test(k)));process.stdout.write(`${JSON.stringify({severity:level.toUpperCase(),service:"taxright-document-agent",...safe})}\n`);}
