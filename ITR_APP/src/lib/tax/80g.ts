export type DonationCategory="FULL_NO_LIMIT"|"HALF_NO_LIMIT"|"FULL_QUALIFYING_LIMIT"|"HALF_QUALIFYING_LIMIT";
export interface DonationInput { donatedRupees:bigint; adjustedGrossTotalIncomeRupees:bigint; category:DonationCategory; mode:"CASH"|"NON_CASH"; evidenceVerified:boolean }
export interface DonationResult { status:"PLANNING"|"EVIDENCE_REQUIRED"|"VERIFIED"|"REJECTED"; qualifyingContributionRupees:bigint; eligibleDeductionRupees:bigint; reason:string }
export function calculate80G(input:DonationInput):DonationResult{
 if(input.mode==="CASH"&&input.donatedRupees>2000n)return{status:"REJECTED",qualifyingContributionRupees:0n,eligibleDeductionRupees:0n,reason:"Cash donations above ₹2,000 are not eligible"};
 const limited=input.category.endsWith("QUALIFYING_LIMIT")&&!input.category.includes("NO_LIMIT");
 const qualifyingLimit=input.adjustedGrossTotalIncomeRupees/10n;
 const qualifying=limited&&input.donatedRupees>qualifyingLimit?qualifyingLimit:input.donatedRupees;
 const eligible=input.category.startsWith("HALF")?qualifying/2n:qualifying;
 return{status:input.evidenceVerified?"VERIFIED":input.donatedRupees>0n?"EVIDENCE_REQUIRED":"PLANNING",qualifyingContributionRupees:qualifying,eligibleDeductionRupees:eligible,reason:limited?"Contribution restricted to 10% of adjusted gross total income before category percentage":"No adjusted-GTI qualifying ceiling for selected category"};
}
