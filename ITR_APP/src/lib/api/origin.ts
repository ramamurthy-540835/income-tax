export function isAllowedRequestOrigin(origin:string,requestUrl:string,appBaseUrl:string):boolean{
 const allowedOrigins=new Set([new URL(appBaseUrl).origin,new URL(requestUrl).origin]);
 return allowedOrigins.has(origin);
}
