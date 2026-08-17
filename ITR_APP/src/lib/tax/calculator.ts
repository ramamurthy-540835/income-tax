import { AY2026_27 as rules } from "./rules/AY2026_27";
import { oldRegimeDeductions } from "./deductions";
import type { Regime, TaxInput, TaxResult } from "./types";
const max0=(n:bigint)=>n<0n?0n:n;
function slabTax(income:bigint, slabs:readonly {from:bigint;to:bigint|null;rate:bigint}[]):bigint{return slabs.reduce((tax,s)=>{if(income<=s.from)return tax;const top=s.to===null?income:(income<s.to?income:s.to);return tax+((top-s.from)*s.rate)/100n;},0n)}
function oldBasic(age:TaxInput["ageBand"]):bigint{return age==="SUPER_SENIOR_80_PLUS"?500000n:age==="SENIOR_60_TO_79"?300000n:250000n}
export function calculateTax(input:TaxInput,regime:Regime):TaxResult{
 let deductions=0n; let trace:TaxResult["trace"]=[]; let taxable:bigint; let tax:bigint;
 if(regime==="OLD"){
  const d=oldRegimeDeductions(input);deductions=d.total;trace=d.trace;taxable=max0(input.grossIncomeRupees-deductions);const basic=oldBasic(input.ageBand);
  tax=slabTax(taxable,[{from:basic,to:500000n,rate:5n},{from:500000n,to:1000000n,rate:20n},{from:1000000n,to:null,rate:30n}]);if(taxable<=500000n&&tax>12500n)tax=12500n;if(taxable<=500000n)tax=0n;
 }else{
  const standard=input.salaryIncomeRupees>0n?rules.limits.newStandardDeductionSalary:0n;deductions=standard;trace=[{section:"16(ia)",submittedRupees:standard,eligibleRupees:standard,reason:"New-regime salary standard deduction",evidenceDocumentIds:[],ruleVersion:rules.ruleVersion}];taxable=max0(input.grossIncomeRupees-deductions);
  tax=slabTax(taxable,[{from:400000n,to:800000n,rate:5n},{from:800000n,to:1200000n,rate:10n},{from:1200000n,to:1600000n,rate:15n},{from:1600000n,to:2000000n,rate:20n},{from:2000000n,to:2400000n,rate:25n},{from:2400000n,to:null,rate:30n}]);if(taxable<=1200000n)tax=0n;
 }
 const cess=(tax*4n+99n)/100n;const total=tax+cess;return{regime,grossIncomeRupees:input.grossIncomeRupees,totalDeductionsRupees:deductions,taxableIncomeRupees:taxable,incomeTaxRupees:tax,cessRupees:cess,totalTaxRupees:total,tdsRupees:input.tdsRupees,estimatedBalanceRupees:total-input.tdsRupees,trace,ruleVersion:rules.ruleVersion};
}
