export interface Metrics{increment(name:string,labels?:Record<string,string>):void;observe(name:string,value:number):void}
export class LogMetrics implements Metrics{increment(name:string,labels={}){process.stdout.write(`${JSON.stringify({metric:name,value:1,...labels})}\n`)}observe(name:string,value:number){process.stdout.write(`${JSON.stringify({metric:name,value})}\n`)}}
