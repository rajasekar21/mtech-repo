-- API Intelligence Platform — PostgreSQL schema init
-- Runs automatically on first container start

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- for BM25-style trigram search

-- ── organizations ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS organizations (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(200) NOT NULL,
    slug        VARCHAR(100) UNIQUE NOT NULL,
    plan        VARCHAR(50) DEFAULT 'free',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── users ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(200),
    role            VARCHAR(50) DEFAULT 'developer',
    org_id          UUID REFERENCES organizations(id) ON DELETE SET NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_org_id ON users(org_id);

-- ── api_specs ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_specs (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id            UUID REFERENCES organizations(id) ON DELETE CASCADE,
    name              VARCHAR(200) NOT NULL,
    version           VARCHAR(50) NOT NULL,
    description       TEXT,
    source_type       VARCHAR(50) NOT NULL DEFAULT 'pdf',
    source_file_path  VARCHAR(500),
    parsed_content    JSONB,
    status            VARCHAR(50) DEFAULT 'pending',
    created_by        UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_specs_org_id ON api_specs(org_id);
CREATE INDEX IF NOT EXISTS idx_api_specs_status ON api_specs(status);

-- ── api_endpoints ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_endpoints (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    spec_id         UUID REFERENCES api_specs(id) ON DELETE CASCADE,
    name            VARCHAR(200) NOT NULL,
    path            VARCHAR(500),
    method          VARCHAR(20),
    description     TEXT,
    request_schema  JSONB,
    response_schema JSONB,
    auth_method     VARCHAR(100),
    tags            JSONB DEFAULT '[]',
    risk_level      VARCHAR(50) DEFAULT 'medium',
    is_deprecated   BOOLEAN DEFAULT FALSE,
    version         VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_endpoints_spec_id ON api_endpoints(spec_id);
CREATE INDEX IF NOT EXISTS idx_endpoints_name_trgm ON api_endpoints USING gin(name gin_trgm_ops);

-- ── api_dependencies ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_dependencies (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    spec_id             UUID REFERENCES api_specs(id) ON DELETE CASCADE,
    source_endpoint_id  UUID REFERENCES api_endpoints(id) ON DELETE CASCADE,
    target_endpoint_id  UUID REFERENCES api_endpoints(id) ON DELETE CASCADE,
    dependency_type     VARCHAR(100) DEFAULT 'calls',
    strength            FLOAT DEFAULT 1.0,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_deps_spec_id ON api_dependencies(spec_id);
CREATE INDEX IF NOT EXISTS idx_deps_source ON api_dependencies(source_endpoint_id);

-- ── api_versions ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_versions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    spec_id         UUID REFERENCES api_specs(id) ON DELETE CASCADE,
    version_number  VARCHAR(50) NOT NULL,
    changelog       JSONB DEFAULT '{}',
    is_current      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── flows ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS flows (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    spec_id         UUID REFERENCES api_specs(id) ON DELETE CASCADE,
    name            VARCHAR(200) NOT NULL,
    type            VARCHAR(100),
    description     TEXT,
    steps           JSONB DEFAULT '[]',
    mermaid_diagram TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_flows_spec_id ON flows(spec_id);

-- ── architecture_entities ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS architecture_entities (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    spec_id     UUID REFERENCES api_specs(id) ON DELETE CASCADE,
    name        VARCHAR(200) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    properties  JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_entities_spec_id ON architecture_entities(spec_id);

-- ── document_chunks ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS document_chunks (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    spec_id     UUID REFERENCES api_specs(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content     TEXT NOT NULL,
    chunk_type  VARCHAR(100) DEFAULT 'general',
    metadata    JSONB DEFAULT '{}',
    embedding   vector(1536),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_spec_id ON document_chunks(spec_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON document_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm ON document_chunks
    USING gin(content gin_trgm_ops);

-- ── security_findings ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS security_findings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    spec_id         UUID REFERENCES api_specs(id) ON DELETE CASCADE,
    endpoint_id     UUID REFERENCES api_endpoints(id) ON DELETE SET NULL,
    severity        VARCHAR(50) NOT NULL DEFAULT 'medium',
    category        VARCHAR(100),
    title           VARCHAR(300) NOT NULL,
    description     TEXT,
    recommendation  TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_findings_spec_id ON security_findings(spec_id);
CREATE INDEX IF NOT EXISTS idx_findings_severity ON security_findings(severity);

-- ── governance_reports ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS governance_reports (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    spec_id         UUID REFERENCES api_specs(id) ON DELETE CASCADE,
    score           FLOAT DEFAULT 0,
    passed_rules    JSONB DEFAULT '[]',
    failed_rules    JSONB DEFAULT '[]',
    recommendations JSONB DEFAULT '[]',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_governance_spec_id ON governance_reports(spec_id);

-- ── impact_reports ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS impact_reports (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    spec_id             UUID REFERENCES api_specs(id) ON DELETE CASCADE,
    endpoint_id         UUID REFERENCES api_endpoints(id) ON DELETE SET NULL,
    change_description  TEXT,
    change_type         VARCHAR(100),
    impacted_endpoints  JSONB DEFAULT '[]',
    impacted_flows      JSONB DEFAULT '[]',
    risk_score          FLOAT DEFAULT 0,
    blast_radius        JSONB DEFAULT '{}',
    security_implications JSONB DEFAULT '[]',
    recommendations     JSONB DEFAULT '[]',
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_impact_spec_id ON impact_reports(spec_id);

-- ── ai_conversations ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_conversations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    org_id          UUID REFERENCES organizations(id) ON DELETE CASCADE,
    title           VARCHAR(300),
    messages        JSONB DEFAULT '[]',
    spec_context_id UUID REFERENCES api_specs(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_convos_user_id ON ai_conversations(user_id);

-- ── Seed default organization and admin user ────────────────────────────
INSERT INTO organizations (id, name, slug, plan)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Default Organization',
    'default',
    'enterprise'
) ON CONFLICT (slug) DO NOTHING;

-- Default admin user: admin@example.com / Admin@123
-- bcrypt hash of "Admin@123"
INSERT INTO users (id, email, hashed_password, full_name, role, org_id)
VALUES (
    '00000000-0000-0000-0000-000000000002',
    'admin@example.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/Lewdqgr6MxYPTDLte',
    'Platform Admin',
    'admin',
    '00000000-0000-0000-0000-000000000001'
) ON CONFLICT (email) DO NOTHING;
