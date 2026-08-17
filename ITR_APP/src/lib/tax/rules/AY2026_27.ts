export const AY2026_27 = {
  assessmentYear: "AY2026-27",
  ruleVersion: "AY2026-27-v1-review-required",
  effectiveDate: "2025-04-01",
  sourceAuthority: "Income Tax Department / CBDT",
  sourceDocument: "Official AY 2026-27 validation rules and enacted Finance Act provisions",
  lastVerifiedAt: "2026-08-17",
  verifiedBy: "ENGINEERING_PENDING_TAX_PROFESSIONAL_SIGN_OFF",
  limits: {
    section80CGroup: 150000n,
    section80CCD1B: 50000n,
    section80DSelfFamilyNonSenior: 25000n,
    section80DSelfFamilySenior: 50000n,
    section80TTA: 10000n,
    section80TTB: 50000n,
    cashDonationMaximum: 2000n,
    oldStandardDeductionSalary: 50000n,
    newStandardDeductionSalary: 75000n
  }
} as const;
