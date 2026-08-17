export type Regime = "OLD" | "NEW";
export type TaxpayerAgeBand = "BELOW_60" | "SENIOR_60_TO_79" | "SUPER_SENIOR_80_PLUS";
export type DeductionStatus = "DETECTED" | "POTENTIALLY_ELIGIBLE" | "EVIDENCE_REQUIRED" | "REVIEW_REQUIRED" | "VERIFIED" | "REJECTED";
export interface TaxTrace { section:string; submittedRupees:bigint; eligibleRupees:bigint; reason:string; evidenceDocumentIds:string[]; ruleVersion:string }
export interface TaxInput { grossIncomeRupees:bigint; salaryIncomeRupees:bigint; tdsRupees:bigint; ageBand:TaxpayerAgeBand; deductions:{ section80CGroup:bigint; section80CCD1B:bigint; section80D:bigint; section80TTA:bigint; section80TTB:bigint; section80G:bigint } }
export interface TaxResult { regime:Regime; grossIncomeRupees:bigint; totalDeductionsRupees:bigint; taxableIncomeRupees:bigint; incomeTaxRupees:bigint; cessRupees:bigint; totalTaxRupees:bigint; tdsRupees:bigint; estimatedBalanceRupees:bigint; trace:TaxTrace[]; ruleVersion:string }
