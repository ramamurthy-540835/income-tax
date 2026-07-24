# E-Filing Preparation Boundary

The backend may mark a workspace `ready_for_portal` only when:

- Taxpayer profile and refund account are complete.
- Every AY-specific ITR-1 eligibility answer is confirmed.
- Normalized return data exists.
- The AY policy has no eligibility blocker.
- A tax calculation workpaper exists.
- An official portal/offline-utility JSON draft exists.
- The draft passes the pinned official JSON Schema and backend root invariants.
- A reviewer approves the workspace.
- The reviewer confirms validation in the current official utility or portal.

The export endpoint remains blocked until these controls pass.

After manual portal submission, record:

- Acknowledgement number
- Filing date and filing section
- Verification status
- Verification date when complete
- Portal-generated acknowledgement/ITR-V as a filing-evidence document

The backend does not store e-Filing passwords, Aadhaar OTPs, EVCs, or portal
sessions. Submission automation must not be added without an authorized ERI/API
integration and a separate security review.
