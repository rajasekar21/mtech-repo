"""Document parsing and chunking service.

Supports PDF (via PyMuPDF + pdfplumber), OpenAPI/Swagger YAML/JSON, and XML.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any, Optional

import yaml
from lxml import etree

from app.core.logging import get_logger

logger = get_logger(__name__)


class DocumentService:
    """Parses API specification documents and splits them into chunks."""

    # ---------------------------------------------------------------------- #
    # PDF
    # ---------------------------------------------------------------------- #

    async def parse_pdf(self, file_path: str) -> list[dict[str, Any]]:
        """Parse a PDF file and return a list of section dicts.

        Uses PyMuPDF for text extraction and pdfplumber for table extraction.

        Args:
            file_path: Absolute path to the PDF file.

        Returns:
            List of dicts with keys: page, type, content, metadata.
        """
        import fitz  # PyMuPDF
        import pdfplumber

        sections: list[dict[str, Any]] = []
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {file_path}")

        # -- PyMuPDF: extract text blocks per page --
        try:
            doc = fitz.open(str(path))
            for page_num, page in enumerate(doc, start=1):
                blocks = page.get_text("blocks")  # list of (x0, y0, x1, y1, text, block_no, block_type)
                for block in blocks:
                    text = block[4].strip()
                    if not text:
                        continue
                    sections.append(
                        {
                            "page": page_num,
                            "type": "text",
                            "content": text,
                            "metadata": {
                                "bbox": block[:4],
                                "block_type": block[6],
                            },
                        }
                    )
            doc.close()
        except Exception as exc:
            logger.warning("PyMuPDF extraction failed", error=str(exc), file=file_path)

        # -- pdfplumber: extract tables --
        try:
            with pdfplumber.open(str(path)) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    tables = page.extract_tables()
                    for table in tables:
                        if not table:
                            continue
                        # Convert table to markdown-like text
                        rows = [" | ".join(str(cell or "") for cell in row) for row in table]
                        table_text = "\n".join(rows)
                        sections.append(
                            {
                                "page": page_num,
                                "type": "table",
                                "content": table_text,
                                "metadata": {"source": "pdfplumber"},
                            }
                        )
        except Exception as exc:
            logger.warning("pdfplumber table extraction failed", error=str(exc), file=file_path)

        logger.info("PDF parsed", file=file_path, sections=len(sections))
        return sections

    # ---------------------------------------------------------------------- #
    # OpenAPI / Swagger
    # ---------------------------------------------------------------------- #

    async def parse_openapi(self, content: str | bytes) -> dict[str, Any]:
        """Parse an OpenAPI/Swagger YAML or JSON spec.

        Args:
            content: Raw spec content (string or bytes).

        Returns:
            Structured dict with keys: info, paths, components, servers.
        """
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")

        # Try YAML first (superset of JSON)
        try:
            raw = yaml.safe_load(content)
        except yaml.YAMLError:
            try:
                raw = json.loads(content)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Content is neither valid YAML nor JSON: {exc}") from exc

        if not isinstance(raw, dict):
            raise ValueError("OpenAPI spec must be a mapping at the top level")

        # Normalise to a consistent structure
        structured: dict[str, Any] = {
            "info": raw.get("info", {}),
            "openapi_version": raw.get("openapi") or raw.get("swagger", "unknown"),
            "paths": raw.get("paths", {}),
            "components": raw.get("components") or raw.get("definitions", {}),
            "servers": raw.get("servers", []),
            "security_schemes": (raw.get("components") or {}).get("securitySchemes", {}),
            "tags": raw.get("tags", []),
            "raw": raw,
        }

        endpoint_count = sum(len(methods) for methods in structured["paths"].values())
        logger.info(
            "OpenAPI spec parsed",
            version=structured["openapi_version"],
            endpoints=endpoint_count,
        )
        return structured

    # ---------------------------------------------------------------------- #
    # XML
    # ---------------------------------------------------------------------- #

    async def parse_xml(self, content: str | bytes) -> dict[str, Any]:
        """Parse an XML API specification (WSDL, RAML, custom).

        Args:
            content: Raw XML content.

        Returns:
            Structured dict representation of the XML.
        """
        if isinstance(content, str):
            content = content.encode("utf-8")

        try:
            root = etree.fromstring(content)
        except etree.XMLSyntaxError as exc:
            raise ValueError(f"Invalid XML content: {exc}") from exc

        def _element_to_dict(element: etree._Element) -> dict[str, Any]:
            result: dict[str, Any] = {}
            # Attributes
            if element.attrib:
                result["@attributes"] = dict(element.attrib)
            # Text content
            text = (element.text or "").strip()
            if text:
                result["#text"] = text
            # Children
            children: dict[str, Any] = {}
            for child in element:
                tag = etree.QName(child.tag).localname
                child_dict = _element_to_dict(child)
                if tag in children:
                    if not isinstance(children[tag], list):
                        children[tag] = [children[tag]]
                    children[tag].append(child_dict)
                else:
                    children[tag] = child_dict
            result.update(children)
            return result

        tag = etree.QName(root.tag).localname
        structured = {
            "root_tag": tag,
            "namespace": etree.QName(root.tag).namespace,
            "content": _element_to_dict(root),
        }

        logger.info("XML spec parsed", root_tag=tag)
        return structured

    # ---------------------------------------------------------------------- #
    # Chunking
    # ---------------------------------------------------------------------- #

    async def chunk_document(
        self,
        sections: list[dict[str, Any]],
        chunk_size: int = 1000,
        overlap: int = 200,
    ) -> list[dict[str, Any]]:
        """Split document sections into overlapping text chunks.

        Args:
            sections: List of section dicts (output of parse_*).
            chunk_size: Maximum characters per chunk.
            overlap: Overlap characters between consecutive chunks.

        Returns:
            List of chunk dicts with keys: chunk_index, content, chunk_type, metadata.
        """
        chunks: list[dict[str, Any]] = []
        chunk_index = 0

        for section in sections:
            text = section.get("content", "")
            if not text:
                continue

            chunk_type = self._classify_chunk_type(text, section.get("type", ""))
            metadata = {
                "page": section.get("page"),
                "section_type": section.get("type"),
                **section.get("metadata", {}),
            }

            if len(text) <= chunk_size:
                chunks.append(
                    {
                        "chunk_index": chunk_index,
                        "content": text,
                        "chunk_type": chunk_type,
                        "metadata": metadata,
                    }
                )
                chunk_index += 1
            else:
                # Sliding window over the text
                start = 0
                while start < len(text):
                    end = min(start + chunk_size, len(text))
                    chunk_text = text[start:end]
                    chunks.append(
                        {
                            "chunk_index": chunk_index,
                            "content": chunk_text,
                            "chunk_type": chunk_type,
                            "metadata": {**metadata, "char_offset": start},
                        }
                    )
                    chunk_index += 1
                    if end == len(text):
                        break
                    start += chunk_size - overlap

        logger.info("Document chunked", total_chunks=len(chunks))
        return chunks

    async def chunk_openapi_spec(
        self,
        parsed: dict[str, Any],
        chunk_size: int = 1000,
        overlap: int = 200,
    ) -> list[dict[str, Any]]:
        """Chunk an already-parsed OpenAPI spec into endpoint-level chunks.

        Each path+method combination becomes at least one chunk, preserving
        full schema context rather than cutting across endpoint boundaries.
        """
        chunks: list[dict[str, Any]] = []
        chunk_index = 0

        # Info block
        info = parsed.get("info", {})
        info_text = (
            f"API: {info.get('title', 'Unknown')}\n"
            f"Version: {info.get('version', 'unknown')}\n"
            f"Description: {info.get('description', '')}"
        )
        chunks.append(
            {
                "chunk_index": chunk_index,
                "content": info_text,
                "chunk_type": "general",
                "metadata": {"section": "info"},
            }
        )
        chunk_index += 1

        # Endpoint chunks
        paths = parsed.get("paths", {})
        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue
            for method, details in methods.items():
                if method.startswith("x-") or method == "parameters":
                    continue
                if not isinstance(details, dict):
                    continue

                endpoint_text = self._serialize_endpoint(path, method, details)
                # Split if too large
                if len(endpoint_text) <= chunk_size:
                    chunks.append(
                        {
                            "chunk_index": chunk_index,
                            "content": endpoint_text,
                            "chunk_type": "api",
                            "metadata": {
                                "path": path,
                                "method": method.upper(),
                                "tags": details.get("tags", []),
                                "operation_id": details.get("operationId"),
                            },
                        }
                    )
                    chunk_index += 1
                else:
                    for start in range(0, len(endpoint_text), chunk_size - overlap):
                        end = min(start + chunk_size, len(endpoint_text))
                        chunks.append(
                            {
                                "chunk_index": chunk_index,
                                "content": endpoint_text[start:end],
                                "chunk_type": "api",
                                "metadata": {
                                    "path": path,
                                    "method": method.upper(),
                                    "char_offset": start,
                                },
                            }
                        )
                        chunk_index += 1
                        if end == len(endpoint_text):
                            break

        # Security schemes
        security_schemes = parsed.get("security_schemes", {})
        if security_schemes:
            sec_text = "Security Schemes:\n" + json.dumps(security_schemes, indent=2)
            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "content": sec_text[:chunk_size],
                    "chunk_type": "security",
                    "metadata": {"section": "security_schemes"},
                }
            )
            chunk_index += 1

        logger.info("OpenAPI spec chunked", total_chunks=len(chunks))
        return chunks

    # ---------------------------------------------------------------------- #
    # Metadata extraction
    # ---------------------------------------------------------------------- #

    async def extract_metadata(self, content: str) -> dict[str, Any]:
        """Extract high-level metadata from raw content text.

        Returns:
            Dict with keys: title, version, description, detected_type.
        """
        metadata: dict[str, Any] = {
            "title": None,
            "version": None,
            "description": None,
            "detected_type": "unknown",
        }

        # Try OpenAPI YAML/JSON
        try:
            parsed = yaml.safe_load(content)
            if isinstance(parsed, dict):
                info = parsed.get("info", {})
                metadata["title"] = info.get("title")
                metadata["version"] = info.get("version") or parsed.get("openapi") or parsed.get("swagger")
                metadata["description"] = info.get("description")
                if "openapi" in parsed or "swagger" in parsed:
                    metadata["detected_type"] = "openapi"
                return metadata
        except Exception:
            pass

        # Try XML detection
        stripped = content.strip()
        if stripped.startswith("<"):
            metadata["detected_type"] = "xml"
            # Extract title-like attributes from XML
            title_match = re.search(r'name=["\']([^"\']+)["\']', stripped[:500])
            if title_match:
                metadata["title"] = title_match.group(1)
            return metadata

        # Plain text / PDF fallback
        lines = content.split("\n")[:20]
        for line in lines:
            line = line.strip()
            if line and not metadata["title"] and len(line) < 200:
                metadata["title"] = line
                break

        metadata["detected_type"] = "text"
        return metadata

    # ---------------------------------------------------------------------- #
    # Helpers
    # ---------------------------------------------------------------------- #

    def _classify_chunk_type(self, text: str, section_type: str) -> str:
        """Heuristically classify chunk content type."""
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["get /", "post /", "put /", "delete /", "patch /", "endpoint", "api path"]):
            return "api"
        if any(kw in text_lower for kw in ["flow", "payment flow", "transaction flow", "sequence"]):
            return "flow"
        if any(kw in text_lower for kw in ["schema", "request body", "response body", "json schema", "type:", "properties:"]):
            return "schema"
        if any(kw in text_lower for kw in ["security", "authentication", "authorization", "oauth", "jwt", "bearer", "api key"]):
            return "security"
        return "general"

    def _serialize_endpoint(self, path: str, method: str, details: dict[str, Any]) -> str:
        """Convert an OpenAPI endpoint dict to a human-readable text block."""
        parts: list[str] = [
            f"Endpoint: {method.upper()} {path}",
        ]
        if details.get("summary"):
            parts.append(f"Summary: {details['summary']}")
        if details.get("description"):
            parts.append(f"Description: {details['description']}")
        if details.get("operationId"):
            parts.append(f"Operation ID: {details['operationId']}")
        if details.get("tags"):
            parts.append(f"Tags: {', '.join(details['tags'])}")

        # Parameters
        params = details.get("parameters", [])
        if params:
            parts.append("Parameters:")
            for param in params[:10]:  # limit to 10 to prevent huge chunks
                param_line = f"  - {param.get('name', '?')} ({param.get('in', '?')}): {param.get('description', '')}"
                parts.append(param_line)

        # Request body
        req_body = details.get("requestBody", {})
        if req_body:
            parts.append("Request Body:")
            parts.append(f"  Required: {req_body.get('required', False)}")
            content_types = list((req_body.get("content") or {}).keys())
            if content_types:
                parts.append(f"  Content-Type: {', '.join(content_types)}")

        # Responses
        responses = details.get("responses", {})
        if responses:
            parts.append("Responses:")
            for code, resp_detail in list(responses.items())[:10]:
                desc = resp_detail.get("description", "") if isinstance(resp_detail, dict) else ""
                parts.append(f"  {code}: {desc}")

        # Security
        security = details.get("security")
        if security:
            parts.append(f"Security: {json.dumps(security)}")

        return "\n".join(parts)
