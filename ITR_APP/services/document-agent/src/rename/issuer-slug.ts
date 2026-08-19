export const issuerSlug=(value:string|null):string=>(value??"UNKNOWN").normalize("NFKD").toUpperCase().replace(/[^A-Z0-9]+/g,"").slice(0,28)||"UNKNOWN";
