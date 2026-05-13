# API Intelligence Platform

**AI-Powered API Intelligence & Impact Analysis Platform**

Transform static API specification documents (PDF / OpenAPI / XML / Swagger / AsyncAPI) into an interactive AI-assisted developer portal. Think SwaggerHub + Backstage + Neo4j Bloom + AI Copilot — all open-source and deployable on bare metal.

---

## Platform Capabilities

| # | Capability | Description |
|---|---|---|
| 1 | **AI Semantic Search** | Natural language queries across all API specs |
| 2 | **Document Ingestion** | PDF, OpenAPI, XML, Swagger, AsyncAPI ingestion |
| 3 | **Knowledge Extraction** | Auto-extract APIs, flows, entities, security rules |
| 4 | **API Catalog** | Enterprise API explorer with filtering, tagging, risk |
| 5 | **Dependency Graph** | Interactive Neo4j + React Flow graph exploration |
| 6 | **Impact Analysis** | Blast radius analysis for any API/schema change |
| 7 | **Flow Visualizer** | Animated Mermaid sequence diagrams |
| 8 | **AI Chat Assistant** | RAG-powered copilot with graph-enhanced retrieval |
| 9 | **Version Comparison** | Diff engine for API changes across versions |
| 10 | **Governance Engine** | Automated naming, auth, security rule validation |
| 11 | **Security Intelligence** | Sensitive data, auth gaps, encryption compliance |
| 12 | **Reuse Recommender** | Prevent duplicate APIs — find reusable components |

---

## Open-Source Stack

| Layer | Technology | License |
|---|---|---|
| **LLM** | Ollama + llama3.2 / mistral / qwen2.5 | MIT |
| **Embeddings** | Ollama nomic-embed-text | MIT |
| **Vector DB** | PostgreSQL + pgvector | Apache 2.0 |
| **Graph DB** | Neo4j 5.x Community | GPL 3.0 |
| **Message Queue** | Redis + Celery | BSD / MIT |
| **Backend** | Python FastAPI + SQLAlchemy | MIT |
| **Frontend** | Next.js 15 + TypeScript + TailwindCSS | MIT |
| **Visualization** | React Flow + Mermaid.js + D3.js | MIT |
| **Monitoring** | Prometheus + Grafana | Apache 2.0 |
| **Container** | Docker + Docker Compose | Apache 2.0 |

> **Optional cloud backend**: Set `AI_BACKEND=openai` with `OPENAI_API_KEY` to use GPT-4o instead of Ollama.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Next.js Frontend                      │
│  Dashboard │ Catalog │ Graph │ Flow │ Chat │ Governance  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP/REST
┌──────────────────────▼──────────────────────────────────┐
│                  FastAPI Backend                         │
│                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ AI Service  │  │ Catalog Svc  │  │  Search Svc   │  │
│  │ (Ollama/GPT)│  │              │  │  (pgvector)   │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Graph Svc   │  │ Impact Svc   │  │  Governance   │  │
│  │  (Neo4j)    │  │              │  │  Engine       │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Doc Ingest  │  │  Chat/RAG    │  │  Auth/JWT     │  │
│  │  Service    │  │  Service     │  │               │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
│                                                         │
│              Celery Workers (async ingestion)           │
└──────┬──────────────────────┬────────────────┬─────────┘
       │                      │                │
┌──────▼──────┐  ┌────────────▼────┐  ┌───────▼──────┐
│ PostgreSQL  │  │     Neo4j       │  │    Redis     │
│ + pgvector  │  │  Graph Database │  │  Task Queue  │
└─────────────┘  └─────────────────┘  └──────────────┘
```

---

## Project Structure

```
api-intelligence-platform/
├── backend/                          # FastAPI Python backend
│   ├── app/
│   │   ├── main.py                   # FastAPI app + routers
│   │   ├── core/
│   │   │   ├── config.py             # Pydantic settings
│   │   │   ├── security.py           # JWT auth
│   │   │   ├── logging.py            # Structured logging
│   │   │   └── middleware.py         # Rate limit, request ID
│   │   ├── api/v1/                   # Route handlers
│   │   │   ├── auth.py
│   │   │   ├── catalog.py
│   │   │   ├── search.py
│   │   │   ├── graph.py
│   │   │   ├── impact.py
│   │   │   ├── governance.py
│   │   │   ├── chat.py
│   │   │   ├── security.py
│   │   │   └── versions.py
│   │   ├── models/                   # SQLAlchemy ORM models
│   │   ├── schemas/                  # Pydantic request/response
│   │   ├── services/                 # Business logic
│   │   │   ├── ai_service.py         # Dual LLM backend
│   │   │   ├── document_service.py   # PDF/XML/OpenAPI parser
│   │   │   ├── ingestion_service.py  # Pipeline orchestrator
│   │   │   ├── search_service.py     # Hybrid semantic search
│   │   │   ├── graph_service.py      # Neo4j operations
│   │   │   ├── impact_service.py     # Blast radius analysis
│   │   │   ├── governance_service.py # Rule validation
│   │   │   ├── chat_service.py       # RAG chat
│   │   │   └── catalog_service.py    # API catalog CRUD
│   │   ├── db/
│   │   │   ├── database.py           # Async SQLAlchemy
│   │   │   └── neo4j.py              # Neo4j driver
│   │   └── workers/
│   │       └── celery_app.py         # Celery task definitions
│   ├── alembic/                      # DB migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                         # Next.js 15 TypeScript
│   ├── src/
│   │   ├── app/                      # App Router pages
│   │   │   ├── page.tsx              # Dashboard
│   │   │   ├── catalog/              # API Catalog
│   │   │   ├── graph/                # Dependency Graph
│   │   │   ├── flow/                 # Flow Visualizer
│   │   │   ├── chat/                 # AI Chat
│   │   │   ├── impact/               # Impact Analysis
│   │   │   ├── governance/           # Governance Dashboard
│   │   │   ├── security/             # Security Intelligence
│   │   │   └── versions/             # Version Comparison
│   │   ├── components/               # Reusable components
│   │   ├── store/                    # Zustand state
│   │   ├── lib/                      # API client, utils
│   │   └── types/                    # TypeScript interfaces
│   ├── package.json
│   └── Dockerfile
├── graph/
│   ├── schema/
│   │   ├── postgres_init.sql         # DB schema + pgvector
│   │   └── neo4j_init.cypher         # Neo4j constraints + seeds
│   └── queries/                      # Reusable Cypher queries
├── k8s/                              # Kubernetes manifests
│   ├── backend/
│   ├── frontend/
│   ├── postgres/
│   ├── neo4j/
│   └── ingress/
├── .github/workflows/
│   ├── ci.yml                        # Lint + test + build
│   └── cd.yml                        # Build + push + deploy
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Quick Start (Docker — recommended)

### Prerequisites
- Docker 24+ and Docker Compose
- 8 GB RAM minimum (16 GB recommended for Ollama)

```bash
# 1. Clone and enter directory
git clone https://github.com/rajasekar21/mtech-repo.git
cd mtech-repo/api-intelligence-platform

# 2. Configure environment
cp .env.example .env
# Edit .env if needed (defaults work for local dev)

# 3. Start all services
docker compose up -d

# Wait ~2-3 min for Ollama to pull llama3.2 model
docker compose logs -f ollama-setup

# 4. Access the platform
open http://localhost:3000        # Frontend portal
open http://localhost:8000/docs   # Backend Swagger UI
open http://localhost:7474        # Neo4j Browser
open http://localhost:8080        # (if kafka-ui added)
open http://localhost:3001        # Grafana monitoring
```

**Default login**: `admin@example.com` / `Admin@123`

---

## Bare Metal Installation

### Prerequisites

| Component | Version | Install |
|---|---|---|
| Python | 3.12+ | system package manager |
| Node.js | 20+ | [nvm](https://github.com/nvm-sh/nvm) |
| PostgreSQL | 16+ | `apt install postgresql-16` |
| pgvector | latest | [pgvector install](https://github.com/pgvector/pgvector) |
| Neo4j | 5.x Community | [neo4j.com/download](https://neo4j.com/download-center/) |
| Redis | 7+ | `apt install redis-server` |
| Ollama | latest | `curl -fsSL https://ollama.com/install.sh \| sh` |

### Step 1: Setup databases

```bash
# PostgreSQL
sudo -u postgres psql -c "CREATE USER api_user WITH PASSWORD 'api_secret';"
sudo -u postgres psql -c "CREATE DATABASE api_intelligence OWNER api_user;"
sudo -u postgres psql -d api_intelligence -c "CREATE EXTENSION vector;"
sudo -u postgres psql -d api_intelligence -f graph/schema/postgres_init.sql

# Neo4j — start service, then run init
neo4j start
cypher-shell -u neo4j -p neo4j_secret < graph/schema/neo4j_init.cypher

# Redis
redis-server --daemonize yes
```

### Step 2: Ollama models

```bash
ollama serve &
ollama pull llama3.2           # LLM (~2 GB)
ollama pull nomic-embed-text   # Embeddings (~274 MB)
```

### Step 3: Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp ../.env.example .env  # edit DATABASE_URL etc.

# Run migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Start Celery worker (separate terminal)
celery -A app.workers.celery_app worker --loglevel=info
```

### Step 4: Frontend

```bash
cd frontend
npm install

NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1 npm run dev
# Open http://localhost:3000
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/auth/login` | Authenticate and get JWT |
| GET | `/api/v1/auth/me` | Current user profile |
| POST | `/api/v1/catalog/specs` | Upload API spec document |
| GET | `/api/v1/catalog/specs` | List all specs (paginated) |
| GET | `/api/v1/catalog/specs/{id}/endpoints` | List endpoints |
| POST | `/api/v1/catalog/specs/{id}/ingest` | Trigger AI ingestion |
| POST | `/api/v1/search` | Semantic/hybrid search |
| GET | `/api/v1/graph/{spec_id}` | Full dependency graph |
| POST | `/api/v1/impact/analyze` | Run impact analysis |
| POST | `/api/v1/governance/validate/{spec_id}` | Governance check |
| POST | `/api/v1/chat` | AI chat message |
| POST | `/api/v1/versions/compare` | Compare two spec versions |
| GET | `/api/v1/security/findings/{spec_id}` | Security findings |

Full interactive docs: `http://localhost:8000/docs`

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `AI_BACKEND` | `ollama` | `ollama` (OSS) or `openai` (cloud) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `OLLAMA_MODEL` | `llama3.2` | Chat model |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |
| `OPENAI_API_KEY` | _(empty)_ | Only needed for `openai` backend |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Postgres connection |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for Celery |
| `SECRET_KEY` | _(required)_ | JWT signing key |

---

## Ingesting the UPI API Specification

1. Log in to the portal at `http://localhost:3000`
2. Click **Upload Specification** in the Catalog
3. Select your UPI API PDF file
4. Enter name: `UPI 2.0 API Specification`, version: `2.0`
5. Click **Upload & Process**

The platform will automatically:
- Parse all pages of the PDF
- Extract API endpoints, schemas, flows
- Build dependency relationships
- Create knowledge graph in Neo4j
- Generate vector embeddings for semantic search
- Run governance validation
- Identify security findings

Processing takes 2–5 minutes depending on document size.

---

## Neo4j Graph Model

```
(API)-[:CALLS]->(API)
(API)-[:DEPENDS_ON]->(API)
(API)-[:AUTHENTICATES_WITH]->(AuthenticationMethod)
(PSP)-[:ROUTES_TO]->(NPCI)
(NPCI)-[:ROUTES_TO]->(Bank)
(Flow)-[:INCLUDES]->(API)
(API)-[:VALIDATES]->(SecurityRule)
(API)-[:IMPACTS]->(API)
(API)-[:REUSES]->(API)
```

---

## Production Deployment (Kubernetes)

```bash
# Create namespace + secrets
kubectl create namespace api-intelligence
kubectl create secret generic backend-secrets \
  --from-env-file=.env -n api-intelligence
kubectl create secret generic postgres-secrets \
  --from-literal=POSTGRES_DB=api_intelligence \
  --from-literal=POSTGRES_USER=api_user \
  --from-literal=POSTGRES_PASSWORD=<secret> \
  -n api-intelligence

# Apply manifests
kubectl apply -f k8s/postgres/
kubectl apply -f k8s/neo4j/
kubectl apply -f k8s/backend/
kubectl apply -f k8s/frontend/
kubectl apply -f k8s/ingress/

# Monitor rollout
kubectl rollout status deployment/backend -n api-intelligence
kubectl rollout status deployment/frontend -n api-intelligence
```

---

## Development

```bash
# Run CI checks locally
cd backend && ruff check app/ && ruff format --check app/
cd frontend && npm run lint && npm run type-check

# Database migrations
cd backend && alembic revision --autogenerate -m "description"
cd backend && alembic upgrade head

# Run tests
cd backend && pytest tests/ -v
cd frontend && npm test
```
