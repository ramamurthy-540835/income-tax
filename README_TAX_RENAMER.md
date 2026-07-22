# Universal Client PDF Renaming Agent

This preview-first Python agent accepts arbitrary client PDFs. It uses
`pdfplumber` for local text extraction, then Gemini or OpenAI vision to identify
text PDFs and image-only scans. It does not assume the document is a tax receipt.

## Setup (Windows PowerShell)

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

Configure either provider:

```powershell
$env:GEMINI_API_KEY = "your-gemini-key"
# OR
$env:OPENAI_API_KEY = "your-openai-key"
```

Do not put API keys in the source code.

## Preview first

Gemini (explicit):

```powershell
py tax_document_renamer.py "C:\Clients\Client A\Documents" --provider gemini --client "Client_A"
```

OpenAI (the backend to use instead of trying to embed Codex itself):

```powershell
py tax_document_renamer.py "C:\Clients\Client A\Documents" --provider openai --client "Client_A"
```

Automatic provider selection uses `GEMINI_API_KEY` first, then
`OPENAI_API_KEY`:

```powershell
py tax_document_renamer.py "C:\Clients\Client A\Documents" --provider auto --client "Client_A"
```

Review the terminal plan and `rename_audit_*.csv`. Only then rename:

```powershell
py tax_document_renamer.py "C:\Clients\Client A\Documents" --provider auto --client "Client_A" --apply
```

Options:

```text
--recursive             Include PDFs in subfolders
--min-confidence 0.80   Skip uncertain identifications
--detail high           OpenAI scan detail (default)
--model MODEL_ID        Override the selected provider model
--apply                 Perform the proposed renames
```

Existing files are never overwritten. Low-confidence documents remain unchanged
for manual review. Generated names exclude PAN, Aadhaar, bank account, phone,
email, and street-address data.

## Important privacy note

`pdfplumber` extraction happens locally, but the PDF and extracted text are then
sent to the chosen AI API so scanned and unfamiliar documents can be classified.
Obtain client authorization and follow your firm's privacy, retention, and
professional-compliance rules.
