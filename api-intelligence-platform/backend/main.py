"""
API Intelligence Platform — simple single-file backend.

Endpoints:
  POST /api/upload          Upload a PDF spec → parse → store
  GET  /api/specs           List all uploaded specs
  GET  /api/specs/{id}      Spec detail + all APIs
  GET  /api/specs/{id}/apis List APIs (with optional ?q= filter)
  GET  /api/search          Search across ALL specs: ?q=mobilenumber&spec_id=...
  DELETE /api/specs/{id}    Remove a spec

Serves the frontend HTML at GET /
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import ApiRecord, SessionLocal, SpecRecord, get_db, init_db
from parser import parse_pdf

UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="API Intelligence Platform", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


# ── Upload ────────────────────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_spec(
    file: UploadFile = File(...),
    name: str = Form(""),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")

    spec_id   = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"{spec_id}_{file.filename}"
    content   = await file.read()
    save_path.write_bytes(content)

    # Parse
    try:
        page_count, sections = parse_pdf(str(save_path))
    except Exception as exc:
        save_path.unlink(missing_ok=True)
        raise HTTPException(500, f"PDF parsing failed: {exc}")

    spec_name = name.strip() or Path(file.filename).stem

    # Store spec
    spec = SpecRecord(
        id         = spec_id,
        name       = spec_name,
        filename   = file.filename,
        page_count = page_count,
        api_count  = len(sections),
    )
    db.add(spec)

    # Store APIs
    for s in sections:
        api = ApiRecord(
            id              = str(uuid.uuid4()),
            spec_id         = spec_id,
            name            = s.name,
            section         = s.section_number,
            description     = s.description,
            request_fields  = json.dumps([f.__dict__ for f in s.request_fields]),
            response_fields = json.dumps([f.__dict__ for f in s.response_fields]),
            raw_text        = s.raw_text[:2000],
        )
        db.add(api)

    db.commit()

    return {
        "spec_id":    spec_id,
        "name":       spec_name,
        "page_count": page_count,
        "api_count":  len(sections),
    }


# ── Specs ─────────────────────────────────────────────────────────────────────

@app.get("/api/specs")
def list_specs(db: Session = Depends(get_db)):
    specs = db.query(SpecRecord).order_by(SpecRecord.uploaded_at.desc()).all()
    return [
        {
            "id":          s.id,
            "name":        s.name,
            "filename":    s.filename,
            "page_count":  s.page_count,
            "api_count":   s.api_count,
            "uploaded_at": s.uploaded_at.isoformat() if s.uploaded_at else None,
        }
        for s in specs
    ]


@app.get("/api/specs/{spec_id}")
def get_spec(spec_id: str, db: Session = Depends(get_db)):
    spec = db.query(SpecRecord).filter(SpecRecord.id == spec_id).first()
    if not spec:
        raise HTTPException(404, "Spec not found")
    apis = db.query(ApiRecord).filter(ApiRecord.spec_id == spec_id).all()
    return {
        "id":          spec.id,
        "name":        spec.name,
        "filename":    spec.filename,
        "page_count":  spec.page_count,
        "api_count":   spec.api_count,
        "uploaded_at": spec.uploaded_at.isoformat() if spec.uploaded_at else None,
        "apis": [_api_dict(a) for a in apis],
    }


@app.get("/api/specs/{spec_id}/apis")
def list_apis(
    spec_id: str,
    q: str = Query("", description="Filter APIs by name or field"),
    db: Session = Depends(get_db),
):
    apis = db.query(ApiRecord).filter(ApiRecord.spec_id == spec_id).all()
    if q:
        ql = q.lower()
        apis = [a for a in apis if _api_matches(a, ql)]
    return [_api_dict(a) for a in apis]


@app.delete("/api/specs/{spec_id}")
def delete_spec(spec_id: str, db: Session = Depends(get_db)):
    db.query(ApiRecord).filter(ApiRecord.spec_id == spec_id).delete()
    deleted = db.query(SpecRecord).filter(SpecRecord.id == spec_id).delete()
    db.commit()
    if not deleted:
        raise HTTPException(404, "Spec not found")
    return {"deleted": True}


# ── Search ────────────────────────────────────────────────────────────────────

@app.get("/api/search")
def search(
    q: str = Query(..., min_length=1, description="Search term, e.g. 'mobilenumber'"),
    spec_id: str = Query("", description="Limit to a specific spec"),
    db: Session = Depends(get_db),
):
    """
    Search all APIs for a field name, description keyword, or API name.
    Returns each matching API with only the matching fields highlighted.
    """
    if not q.strip():
        return []

    ql = q.strip().lower()
    query = db.query(ApiRecord)
    if spec_id:
        query = query.filter(ApiRecord.spec_id == spec_id)
    apis = query.all()

    results = []
    for api in apis:
        req_matches  = _matching_fields(api.request_fields_list(),  ql)
        resp_matches = _matching_fields(api.response_fields_list(), ql)
        name_match   = ql in api.name.lower() or ql in (api.description or "").lower()

        if req_matches or resp_matches or name_match:
            results.append({
                "spec_id":         api.spec_id,
                "api_id":          api.id,
                "api_name":        api.name,
                "section":         api.section,
                "description":     api.description,
                "name_match":      name_match,
                "request_matches": req_matches,
                "response_matches": resp_matches,
                "total_matches":   len(req_matches) + len(resp_matches) + (1 if name_match else 0),
            })

    # Sort: most matches first
    results.sort(key=lambda r: r["total_matches"], reverse=True)

    # Attach spec names
    spec_ids  = {r["spec_id"] for r in results}
    spec_map  = {
        s.id: s.name
        for s in db.query(SpecRecord).filter(SpecRecord.id.in_(spec_ids)).all()
    }
    for r in results:
        r["spec_name"] = spec_map.get(r["spec_id"], "")

    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _api_dict(a: ApiRecord) -> dict:
    return {
        "id":              a.id,
        "name":            a.name,
        "section":         a.section,
        "description":     a.description,
        "request_fields":  a.request_fields_list(),
        "response_fields": a.response_fields_list(),
    }


def _api_matches(a: ApiRecord, ql: str) -> bool:
    if ql in a.name.lower() or ql in (a.description or "").lower():
        return True
    for f in a.request_fields_list() + a.response_fields_list():
        if ql in f.get("name", "").lower() or ql in f.get("description", "").lower():
            return True
    return False


def _matching_fields(fields: list[dict], ql: str) -> list[dict]:
    out = []
    for f in fields:
        if ql in f.get("name", "").lower() or ql in f.get("description", "").lower():
            out.append(f)
    return out


# ── Frontend (single HTML page) ───────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def frontend():
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    return HTMLResponse("<h1>API Intelligence Platform</h1><p>Frontend not found.</p>")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
