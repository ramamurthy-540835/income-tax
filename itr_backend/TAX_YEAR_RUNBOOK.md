# Adding an Assessment Year

Never copy the previous year's limits and enable them unchanged.

1. Download the notified ITR-1 form, JSON Schema, schema change document, and
   validation rules from the official Income Tax Department downloads page.
2. Record release dates and calculate checksums for all official artifacts.
3. Add `itr_agent/schemas/AY_<year>/` and preserve the original schema encoding.
4. Add a new `TaxYearPolicy` module with `enabled=False`.
5. Implement eligibility, slab, rebate, deduction, house-property, capital-gain,
   filing-section, interest, and fee changes for the new year.
6. Implement policy-level invariants not expressed by the JSON Schema.
7. Add official positive/negative fixtures and boundary tests.
8. Compare calculations and generated workpapers with the current official
   offline utility.
9. Review all portal Category A, B, and D validation changes.
10. Obtain tax-preparer approval, update the registry, and set `enabled=True`.

Customer IDs, user access, and historical filing evidence are reused. Return
figures, documents, calculations, schema validation, portal validation, and
approval are always AY-specific.

Official downloads:

https://www.incometax.gov.in/iec/foportal/downloads
