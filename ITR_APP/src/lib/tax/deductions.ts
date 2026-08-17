import { AY2026_27 as rules } from "./rules/AY2026_27";
import type { TaxInput, TaxTrace } from "./types";
const min=(a:bigint,b:bigint)=>a<b?a:b;
export function oldRegimeDeductions(input:TaxInput):{total:bigint;trace:TaxTrace[]}{
 const l=rules.limits; const trace:TaxTrace[]=[];
 const add=(section:string,submitted:bigint,eligible:bigint,reason:string)=>trace.push({section,submittedRupees:submitted,eligibleRupees:eligible,reason,evidenceDocumentIds:[],ruleVersion:rules.ruleVersion});
 const s80c=min(input.deductions.section80CGroup,l.section80CGroup); add("80C/80CCC/80CCD(1)",input.deductions.section80CGroup,s80c,"Combined statutory ceiling applied");
 const nps=min(input.deductions.section80CCD1B,l.section80CCD1B); add("80CCD(1B)",input.deductions.section80CCD1B,nps,"Additional NPS ceiling applied");
 const dLimit=input.ageBand==="BELOW_60"?l.section80DSelfFamilyNonSenior:l.section80DSelfFamilySenior; const d=min(input.deductions.section80D,dLimit); add("80D",input.deductions.section80D,d,"Age-dependent ceiling applied; parent premiums require separate facts");
 const interest=input.ageBand==="BELOW_60"?min(input.deductions.section80TTA,l.section80TTA):min(input.deductions.section80TTB,l.section80TTB); add(input.ageBand==="BELOW_60"?"80TTA":"80TTB",input.ageBand==="BELOW_60"?input.deductions.section80TTA:input.deductions.section80TTB,interest,"Applicable savings/deposit interest ceiling applied");
 const salaryStandard=input.salaryIncomeRupees>0n?l.oldStandardDeductionSalary:0n; add("16(ia)",salaryStandard,salaryStandard,"Old-regime salary standard deduction");
 const donation=input.deductions.section80G; add("80G",donation,donation,"Amount must already be validated by category, adjusted-GTI limit, payment mode and evidence");
 return {total:s80c+nps+d+interest+salaryStandard+donation,trace};
}
