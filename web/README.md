# AIDIRAC Tax Desk frontend

Next.js interface for the existing FastAPI tax workspace. It supports:

- client creation and PAN/DOB profile entry;
- automatic AIS password handling by the backend;
- batch PDF/image intake with automatic classification and contextual naming;
- paste-first notice and outstanding-demand analysis;
- evidence-linked response drafting and risk display.

Run the backend in development mode:

```powershell
$env:ENVIRONMENT="development"
$env:AUTH_MODE="development"
$env:GCP_PROJECT_ID="aidirac-503309"
$env:GCS_BUCKET_NAME="aidirac-503309-income-tax-prod"
.\.venv\Scripts\python.exe -m uvicorn itr_backend.app:app --reload
```

Run the frontend:

```powershell
cd web
npm.cmd run dev
```

The frontend uses `http://localhost:8000` by default. For another backend URL,
copy `.env.example` to `.env.local` and change `NEXT_PUBLIC_API_URL`. This is
infrastructure configuration only; client PAN, DOB, and AIS passwords never
belong in an environment file.
