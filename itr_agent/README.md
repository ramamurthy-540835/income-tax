# Reusable ITR Preparation Agent

This is a review-first workspace and CLI for an Indian tax practice. It supports
ordinary-rate salary/interest ITR-1 candidates for AY 2026-27 and defaults new
client workspaces to the old regime when requested.

Workflow:

1. Store untouched evidence under `01_source`.
2. Hash documents into `02_extracted/evidence_manifest.json`.
3. Extract and review normalized facts in `02_extracted`.
4. Calculate regime and deduction workpapers in `03_workpapers`.
5. Validate an official portal JSON against the downloaded government schema.
6. Upload and e-verify manually after preparer review.

The agent does not automate login, OTP, submission, or e-verification. It does
not issue donation receipts or Form 10BE; those must come from the donee and
match Form 10BD reporting.

## Create a reusable client workspace

```powershell
..\.venv\Scripts\python.exe itr_agent\itr_filing_agent.py init `
  "Clients\Client_001_AY_2026-27" --client-id Client_001 --regime old
```

Place PDFs in the appropriate `01_source` folders and index them:

```powershell
..\.venv\Scripts\python.exe itr_agent\itr_filing_agent.py index `
  "Clients\Client_001_AY_2026-27"
```

## Calculate and validate

```powershell
..\.venv\Scripts\python.exe itr_agent\itr_filing_agent.py calculate `
  Clients\Client_001_AY_2026-27

..\.venv\Scripts\python.exe itr_agent\itr_filing_agent.py validate-80g `
  Clients\Client_001_AY_2026-27

..\.venv\Scripts\python.exe itr_agent\itr_filing_agent.py readiness `
  Clients\Client_001_AY_2026-27
```

Add a genuine, donee-supported 80G donation and validate it immediately:

```powershell
..\.venv\Scripts\python.exe itr_agent\itr_filing_agent.py add-80g CLIENT_FOLDER `
  --donee-name "Donee Name" --donee-pan ABCDE1234F `
  --donee-address "Address from Form 10BE" --urn "80G URN" `
  --category 50_with_limit --amount 230000 --payment-date 2026-03-01 `
  --payment-mode bank_transfer --payment-reference "Bank reference" `
  --receipt-number "Receipt number" --receipt-file "path\receipt.pdf" `
  --form10be-file "path\form10be.pdf"
```

Validate a completed official-format JSON:

```powershell
..\.venv\Scripts\python.exe itr_agent\itr_filing_agent.py validate-portal-json `
  Clients\Client_001_AY_2026-27 `
  --schema itr_agent\schemas\AY_2026-27\ITR-1_2026_Main_V1.1.json `
  --portal-json Clients\Client_001_AY_2026-27\04_portal_export\ITR1.json
```

The calculator stops for business income, foreign assets, special-rate income,
income at or above Rs 50 lakh, multiple house properties, brought-forward
losses, or other facts requiring ITR-2/ITR-3 handling.

Passwords belong only in the root `.env`; never put them in client JSON files.
