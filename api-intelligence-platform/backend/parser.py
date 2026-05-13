"""
PDF parser for API specification documents.

Strategy:
  1. Extract all text + tables per page using pdfplumber.
  2. Detect API section headings using common patterns
     (numbered sections, "Req"/"Resp" prefixes, "API Name" markers).
  3. Under each heading, extract parameter tables — rows become field dicts
     with keys: name, type, size, mandatory, description.
  4. Return a list of ApiSection dicts ready for storage.
"""
from __future__ import annotations

import re
import json
from dataclasses import dataclass, field, asdict
from typing import Any

import pdfplumber


# ── Heading patterns ──────────────────────────────────────────────────────────
_SECTION_RE = re.compile(
    r"^\s*(\d+[\.\d]*)\s+"          # numbered: "2.1 "
    r"(Req\w+|Resp\w+|[A-Z][A-Za-z\s]{3,50})\s*$",
    re.MULTILINE,
)
_API_NAME_RE = re.compile(
    r"\b(Req[A-Z]\w+|Resp[A-Z]\w+)\b"
)
_TABLE_HEADER_WORDS = {"field", "name", "type", "mandatory", "description",
                       "parameter", "element", "data", "size", "length",
                       "format", "remarks", "value", "presence", "tag"}


@dataclass
class ApiField:
    name:        str = ""
    type:        str = ""
    size:        str = ""
    mandatory:   str = ""
    description: str = ""

    def matches(self, query: str) -> bool:
        q = query.lower()
        return (
            q in self.name.lower()
            or q in self.description.lower()
            or q in self.type.lower()
        )


@dataclass
class ApiSection:
    name:            str = ""
    section_number:  str = ""
    description:     str = ""
    request_fields:  list[ApiField] = field(default_factory=list)
    response_fields: list[ApiField] = field(default_factory=list)
    raw_text:        str = ""

    def to_dict(self) -> dict:
        return {
            "name":            self.name,
            "section_number":  self.section_number,
            "description":     self.description,
            "request_fields":  [asdict(f) for f in self.request_fields],
            "response_fields": [asdict(f) for f in self.response_fields],
            "raw_text":        self.raw_text,
        }


# ── Table helpers ─────────────────────────────────────────────────────────────

def _is_header_row(row: list[str | None]) -> bool:
    cells = [str(c or "").strip().lower() for c in row]
    return sum(1 for c in cells if any(w in c for w in _TABLE_HEADER_WORDS)) >= 2


def _parse_table(rows: list[list[str | None]]) -> tuple[list[str], list[ApiField]]:
    """Return (column_headers, fields) from a pdfplumber table."""
    if not rows:
        return [], []

    # find header row
    header_idx = 0
    for i, row in enumerate(rows[:5]):
        if _is_header_row(row):
            header_idx = i
            break

    headers = [str(c or "").strip().lower() for c in rows[header_idx]]
    fields: list[ApiField] = []

    # map column positions
    col = _col_map(headers)

    for row in rows[header_idx + 1:]:
        cells = [str(c or "").strip() for c in row]
        if not any(cells):
            continue
        f = ApiField(
            name        = _get(cells, col.get("name")),
            type        = _get(cells, col.get("type")),
            size        = _get(cells, col.get("size")),
            mandatory   = _get(cells, col.get("mandatory")),
            description = _get(cells, col.get("description")),
        )
        if f.name:
            fields.append(f)

    return headers, fields


def _col_map(headers: list[str]) -> dict[str, int]:
    """Map semantic column names to indexes."""
    mapping: dict[str, int] = {}
    priority = {
        "name":        ["field name", "tag name", "parameter", "element name", "field", "name", "tag"],
        "type":        ["data type", "type", "format"],
        "size":        ["size", "length", "max length", "max"],
        "mandatory":   ["mandatory", "presence", "required", "m/o", "req"],
        "description": ["description", "remarks", "value", "comment", "details"],
    }
    for sem, candidates in priority.items():
        for i, h in enumerate(headers):
            if any(c in h for c in candidates) and sem not in mapping:
                mapping[sem] = i
    # fallback: first col = name, last = description
    if "name" not in mapping and headers:
        mapping["name"] = 0
    if "description" not in mapping and len(headers) > 1:
        mapping["description"] = len(headers) - 1
    return mapping


def _get(cells: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(cells):
        return ""
    return cells[idx]


# ── Section detection ─────────────────────────────────────────────────────────

def _looks_like_heading(text: str) -> tuple[str, str] | None:
    """Return (section_num, api_name) or None."""
    text = text.strip()
    # numbered + Req/Resp pattern
    m = re.match(r"^(\d+[\.\d]*)\s+((?:Req|Resp)\w+)\b", text)
    if m:
        return m.group(1), m.group(2)
    # just a Req/Resp word alone on a short line
    if re.match(r"^(Req[A-Z]\w+|Resp[A-Z]\w+)\s*$", text):
        return "", text.strip()
    # "X.Y API Name:" style
    m2 = re.match(r"^(\d+[\.\d]*)\s+([A-Z][A-Za-z\s]{3,40})\s*[:\-]?\s*$", text)
    if m2 and any(kw in m2.group(2) for kw in ["Request", "Response", "API", "Message", "Transaction"]):
        return m2.group(1), m2.group(2).strip()
    return None


# ── Main parser ───────────────────────────────────────────────────────────────

def parse_pdf(file_path: str) -> tuple[int, list[ApiSection]]:
    """
    Parse a PDF and return (page_count, list[ApiSection]).
    Works for UPI-style specs with numbered sections and parameter tables.
    """
    sections: list[ApiSection] = []
    current: ApiSection | None = None
    in_request  = True   # True = request table, False = response table

    with pdfplumber.open(file_path) as pdf:
        page_count = len(pdf.pages)

        for page in pdf.pages:
            # ── Extract tables from this page ──────────────────────────
            page_tables = page.extract_tables() or []
            table_fields: list[ApiField] = []
            for tbl in page_tables:
                _, fields = _parse_table(tbl)
                table_fields.extend(fields)

            # ── Extract text lines ─────────────────────────────────────
            text = page.extract_text() or ""
            lines = text.split("\n")

            field_ptr = 0   # index into table_fields for assignment

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue

                # Detect section heading
                heading = _looks_like_heading(stripped)
                if heading:
                    if current is not None:
                        sections.append(current)
                    current = ApiSection(
                        name           = heading[1],
                        section_number = heading[0],
                    )
                    in_request = True
                    field_ptr  = 0
                    continue

                if current is None:
                    continue

                # Accumulate raw text
                current.raw_text += stripped + " "

                # Detect request/response delimiter
                low = stripped.lower()
                if any(kw in low for kw in ["request parameter", "request element", "request field", "input parameter"]):
                    in_request = True
                elif any(kw in low for kw in ["response parameter", "response element", "response field", "output parameter"]):
                    in_request = False

                # First non-empty description line → section description
                if not current.description and len(stripped) > 20 and not heading:
                    current.description = stripped

            # Assign table fields extracted on this page to current section
            if current is not None and table_fields:
                if in_request:
                    current.request_fields.extend(table_fields)
                else:
                    current.response_fields.extend(table_fields)

        if current is not None:
            sections.append(current)

    # Post-process: deduplicate fields, remove empty sections
    result = []
    for s in sections:
        s.request_fields  = _dedup(s.request_fields)
        s.response_fields = _dedup(s.response_fields)
        if s.name:
            result.append(s)

    return page_count, result


def _dedup(fields: list[ApiField]) -> list[ApiField]:
    seen: set[str] = set()
    out: list[ApiField] = []
    for f in fields:
        key = f.name.lower()
        if key and key not in seen:
            seen.add(key)
            out.append(f)
    return out
