"""
Seed the API Intelligence Platform with UPI 2.0 API Specification data.

Reads upi_seed_data.json and inserts into PostgreSQL (via SQLAlchemy)
and Neo4j (via Cypher). Run after `alembic upgrade head`.

Usage:
    cd api-intelligence-platform/backend
    python ../graph/seeds/seed_upi.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

# ── resolve imports ───────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import asyncpg
from app.core.config import settings

SEED_FILE = Path(__file__).parent / "upi_seed_data.json"
ORG_ID    = "00000000-0000-0000-0000-000000000001"
USER_ID   = "00000000-0000-0000-0000-000000000002"


async def seed():
    data = json.loads(SEED_FILE.read_text())
    conn = await asyncpg.connect(
        settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    )

    try:
        # ── Create spec ───────────────────────────────────────────────
        spec = data["spec"]
        spec_id = str(uuid.uuid4())
        await conn.execute("""
            INSERT INTO api_specs (id, org_id, name, version, description, source_type, status, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, 'ready', $7)
            ON CONFLICT DO NOTHING
        """, spec_id, ORG_ID, spec["name"], spec["version"],
            spec["description"], spec["source_type"], USER_ID)
        print(f"✓ Spec created: {spec['name']} v{spec['version']} ({spec_id})")

        # ── Architecture entities ──────────────────────────────────────
        for entity in data["architecture_entities"]:
            eid = str(uuid.uuid4())
            await conn.execute("""
                INSERT INTO architecture_entities (id, spec_id, name, entity_type, properties)
                VALUES ($1, $2, $3, $4, $5)
            """, eid, spec_id, entity["name"], entity["entity_type"],
                json.dumps(entity["properties"]))
        print(f"✓ {len(data['architecture_entities'])} architecture entities seeded")

        # ── API Endpoints ──────────────────────────────────────────────
        endpoint_map: dict[str, str] = {}
        for ep in data["api_endpoints"]:
            eid = str(uuid.uuid4())
            endpoint_map[ep["name"]] = eid
            await conn.execute("""
                INSERT INTO api_endpoints
                  (id, spec_id, name, path, method, description, request_schema,
                   response_schema, auth_method, tags, risk_level)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            """, eid, spec_id, ep["name"], ep["path"], ep["method"],
                ep["description"], json.dumps(ep["request_schema"]),
                json.dumps(ep["response_schema"]), ep["auth_method"],
                json.dumps(ep["tags"]), ep["risk_level"])
        print(f"✓ {len(data['api_endpoints'])} API endpoints seeded")

        # ── Flows ─────────────────────────────────────────────────────
        for flow in data["flows"]:
            fid = str(uuid.uuid4())
            await conn.execute("""
                INSERT INTO flows (id, spec_id, name, type, description, steps, mermaid_diagram)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
            """, fid, spec_id, flow["name"], flow["type"], flow["description"],
                json.dumps(flow["steps"]), flow["mermaid_diagram"])
        print(f"✓ {len(data['flows'])} flows seeded")

        # ── Dependencies ──────────────────────────────────────────────
        inserted_deps = 0
        for dep in data["dependencies"]:
            src_id = endpoint_map.get(dep["source"])
            tgt_id = endpoint_map.get(dep["target"])
            if src_id and tgt_id:
                did = str(uuid.uuid4())
                await conn.execute("""
                    INSERT INTO api_dependencies
                      (id, spec_id, source_endpoint_id, target_endpoint_id, dependency_type)
                    VALUES ($1,$2,$3,$4,$5)
                """, did, spec_id, src_id, tgt_id, dep["type"])
                inserted_deps += 1
        print(f"✓ {inserted_deps} dependencies seeded")

        # ── Security findings ─────────────────────────────────────────
        for finding in data["security_findings"]:
            sfid = str(uuid.uuid4())
            await conn.execute("""
                INSERT INTO security_findings
                  (id, spec_id, severity, category, title, description, recommendation)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
            """, sfid, spec_id, finding["severity"], finding["category"],
                finding["title"], finding["description"], finding["recommendation"])
        print(f"✓ {len(data['security_findings'])} security findings seeded")

        print("\n✅ UPI seed data loaded successfully!")
        print(f"   Spec ID: {spec_id}")
        print("   Login: admin@example.com / Admin@123")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
