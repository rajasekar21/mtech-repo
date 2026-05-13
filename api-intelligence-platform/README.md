# API Intelligence Platform

Upload an API specification PDF and instantly browse all APIs with their request/response fields. Search any field name (e.g. `mobilenumber`, `txnId`, `vpa`) to see every API that contains it.

## What it does

1. **Upload** — drag-and-drop a PDF (UPI spec, Swagger, any API doc)
2. **Browse** — all extracted APIs organized with request and response field tables
3. **Search** — type any field name or keyword → see every API containing it, with the matching fields highlighted

## Quick start

### Docker (recommended)

```bash
cd api-intelligence-platform
docker compose up
# Open http://localhost:8000
```

### Local (bare metal)

```bash
cd api-intelligence-platform/backend
pip install -r requirements.txt
python main.py
# Open http://localhost:8000
```

## How to use

1. Open `http://localhost:8000`
2. Drop your UPI API spec PDF onto the upload area (or click to browse)
3. Click **Upload & Parse** — the platform extracts all APIs in seconds
4. **Browse** tab — click any API card to expand it and see all fields
5. **Search** — type in the search box, e.g.:
   - `mobile` → shows all APIs with a mobile number field
   - `txnId` → shows all APIs using transaction ID
   - `vpa` → shows all APIs involving Virtual Payment Address
   - `mandatory` or `M` → filters by mandatory fields
   - `balance` → finds balance-related fields across all APIs

## Search example

Searching `mobile`:

```
ReqPay        → Request: device.mobile (string, M, "10 digit mobile number")
ReqBalEnq     → Request: device.mobile (string, M, "10 digit mobile number")
ReqRegMob     → Request: mobile (string, M, "Registered mobile number")
ReqOtp        → Request: mobile (string, M, "Mobile number for OTP")
```

## Stack

| Component | Technology |
|---|---|
| Backend | Python FastAPI |
| PDF parsing | pdfplumber + PyMuPDF |
| Database | SQLite (no setup needed) |
| Frontend | Single HTML page (no build step) |

No Docker required for local use. No external services. No API keys.
