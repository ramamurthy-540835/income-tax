import { execFileSync } from "node:child_process";
const files=execFileSync("rg",["--files","-g","!node_modules/**","-g","!.next/**","-g","!coverage/**","-g","!playwright-report/**"],{encoding:"utf8"}).trim().split(/\r?\n/).filter(Boolean);
const forbidden=[/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/,/AIza[0-9A-Za-z_-]{30,}/,/service_account\s*"?\s*:/i,/FIREBASE_PRIVATE_KEY\s*=\s*[^\s<]/];
const fs=await import("node:fs/promises");let failures=[];
for(const file of files){const text=await fs.readFile(file,"utf8").catch(()=>"");if(forbidden.some(pattern=>pattern.test(text))&&!file.endsWith(".env.example"))failures.push(file)}
if(failures.length){console.error(`Potential secrets detected in ${failures.length} tracked file(s).`);process.exit(1)}
console.log(`Secret scan passed for ${files.length} project files.`);
