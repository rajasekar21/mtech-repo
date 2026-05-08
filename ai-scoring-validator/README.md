# AI Scoring Validator — UPI Balance Enquiry

AI-powered deployment gate that validates UPI Balance Enquiry API transactions
against the canonical NPCI schema, scores them using a local LLM, and decides
whether a build is ready to promote to the next environment.

**100 % open-source. Runs entirely on bare metal — no cloud API required.**

## Architecture Diagram

[**View Architecture Diagram**](https://htmlpreview.github.io/?https://github.com/rajasekar21/mtech-repo/blob/claude/ai-scoring-validator-xN31p/ai-scoring-validator/architecture.html)

---

## Open-Source Stack

| Component | Technology | License |
|---|---|---|
| LLM (default) | [Ollama](https://ollama.com) + llama3.2 / mistral / qwen2.5 | MIT |
| LLM (optional) | Anthropic Claude API | Commercial |
| Message broker | Apache Kafka 3.7 — KRaft mode (no ZooKeeper) | Apache 2.0 |
| Kafka UI | provectuslabs/kafka-ui | Apache 2.0 |
| APM | Prometheus | Apache 2.0 |
| API framework | FastAPI + Uvicorn | MIT |
| Schema validation | Pydantic v2 | MIT |
| Kafka client | kafka-python | Apache 2.0 |

---

## How It Works

```
Ingestion → Schema Validation → AI Scoring → Deployment Gate
```

| Stage | Component | Description |
|---|---|---|
| **Ingestion** | Kafka Consumer | Consumes `upi.balEnq.raw` topic in windowed batches; falls back to in-memory queue |
| | UPI Simulator | Generates synthetic transactions (75% valid / 15% invalid / 10% edge) |
| | Log Consumer | Reads NDJSON log files as fallback; doubles as audit trail writer |
| **Validation** | Schema Validator | Validates every field against NPCI UPI 2.0 spec using Pydantic |
| **AI Scoring** | Ollama LLM | Scores batch 0–100; model stays loaded in RAM after first call |
| **Gate** | Deployment Gate | PROMOTE ≥ 85 · REVIEW 70–84 · BLOCK < 70 |

### Scoring Breakdown (100 pts total)

| Dimension | Points | What is measured |
|---|---|---|
| Schema compliance | 40 | % of transactions passing all field validations |
| Field quality | 25 | Recurring errors, HMAC issues, masked-field violations |
| Anomaly patterns | 20 | Duplicate txnIds, future timestamps, zero-balance anomalies |
| APM health | 15 | Latency p99, error rate, TPS from Prometheus or computed |

### Validation Source Decision

| Source | Role | Why |
|---|---|---|
| **Kafka Streams** | Primary | Real-time, replayable, schema-aware; mirrors production UPI message flow |
| Structured Logs | Fallback + Audit | Post-hoc revalidation; every record is written here regardless of validity |
| APM / Prometheus | Supplementary | Feeds latency and error-rate signal into the AI scorer (15 pts) |

---

## Project Structure

```
ai-scoring-validator/
├── schema/
│   └── upi_balance_enquiry.py    # Pydantic models — NPCI UPI 2.0 request/response
├── simulator/
│   └── upi_simulator.py          # Synthetic transaction generator
├── validator/
│   └── schema_validator.py       # Field-level validation engine
├── scorer/
│   └── ai_scorer.py              # Dual-backend AI scorer (Ollama / Anthropic)
├── pipeline/
│   ├── kafka_consumer.py         # Kafka primary consumer + in-memory fallback
│   ├── log_consumer.py           # NDJSON log reader and audit writer
│   └── apm_collector.py          # Prometheus scrape or computed APM metrics
├── gate/
│   └── deployment_gate.py        # Tiered promotion gate + audit log
├── api/
│   └── server.py                 # FastAPI REST endpoints
├── config/
│   └── settings.py               # Environment-based configuration
├── main.py                       # CLI orchestrator
├── architecture.html             # Interactive architecture diagram (dark/light)
├── docker-compose.yml            # Full open-source stack
├── Dockerfile
└── requirements.txt
```

---

## Bare Metal Installation

Everything can run directly on a Linux/macOS server without Docker.

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | `python3 --version` |
| Java | 17+ | Required for Kafka bare metal |
| curl | any | For Ollama installer |

### 1. Install Ollama (LLM server)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &                   # starts server on :11434
ollama pull llama3.2             # ~2 GB — default model
```

Other supported models (swap via `OLLAMA_MODEL` env var):

```bash
ollama pull mistral              # 4.1 GB — strong reasoning
ollama pull qwen2.5              # 4.7 GB — multilingual, code-capable
ollama pull llama3.1:8b          # 4.7 GB — larger Llama variant
```

### 2. Install Apache Kafka (KRaft mode — no ZooKeeper)

```bash
# Download Apache Kafka 3.7
curl -O https://downloads.apache.org/kafka/3.7.0/kafka_2.13-3.7.0.tgz
tar -xzf kafka_2.13-3.7.0.tgz
cd kafka_2.13-3.7.0

# Generate cluster UUID and format storage (KRaft — one-time setup)
KAFKA_CLUSTER_ID=$(bin/kafka-storage.sh random-uuid)
bin/kafka-storage.sh format -t $KAFKA_CLUSTER_ID -c config/kraft/server.properties

# Start Kafka broker
bin/kafka-server-start.sh config/kraft/server.properties &

# Create topic
bin/kafka-topics.sh --create --topic upi.balEnq.raw \
  --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
```

### 3. Install Prometheus (optional — for APM metrics)

```bash
curl -LO https://github.com/prometheus/prometheus/releases/download/v2.51.0/prometheus-2.51.0.linux-amd64.tar.gz
tar -xzf prometheus-2.51.0.linux-amd64.tar.gz
cd prometheus-2.51.0.linux-amd64
./prometheus --config.file=<path-to>/ai-scoring-validator/prometheus.yml &
```

### 4. Install Python dependencies

```bash
cd ai-scoring-validator
pip install -r requirements.txt
```

### 5. Run

```bash
# One-shot simulation (no Kafka needed)
python main.py simulate --count 200

# REST API server
python main.py serve

# Continuous Kafka stream
python main.py kafka --topic upi.balEnq.raw
```

---

## Docker Quick Start (all-in-one)

```bash
docker compose up
```

This starts all services — no configuration needed:

| Service | Port | Description |
|---|---|---|
| `ollama` | 11434 | LLM server (llama3.2 pulled automatically) |
| `kafka` | 9092 | Apache Kafka 3.7 (KRaft, no ZooKeeper) |
| `kafka-ui` | 8080 | Kafka UI |
| `prometheus` | 9090 | Metrics |
| `validator-api` | 8000 | Scoring Validator REST API |

---

## Configuration

All settings via environment variables:

| Variable | Default | Description |
|---|---|---|
| `LLM_BACKEND` | `ollama` | `ollama` (open-source) or `anthropic` (cloud) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | Model to use (any model pulled in Ollama) |
| `ANTHROPIC_API_KEY` | _(empty)_ | Only needed when `LLM_BACKEND=anthropic` |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker address |
| `KAFKA_TOPIC_RAW` | `upi.balEnq.raw` | Topic to consume |
| `KAFKA_GROUP_ID` | `ai-scoring-validator` | Consumer group ID |
| `KAFKA_BATCH_SIZE` | `100` | Records per scoring window |
| `KAFKA_BATCH_TIMEOUT_S` | `30` | Max wait before scoring partial batch |
| `PROMETHEUS_URL` | _(optional)_ | Prometheus base URL for APM scrape |
| `PROMOTE_THRESHOLD` | `85` | Minimum score to auto-promote |
| `REVIEW_THRESHOLD` | `70` | Minimum score to require manual review |
| `AUDIT_LOG_PATH` | `./logs/audit.ndjson` | Audit trail output path |
| `FROM_ENV` | `staging` | Source environment label |
| `TO_ENV` | `production` | Target environment label |

---

## REST API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Liveness probe |
| `/simulate` | POST | Generate synthetic transactions |
| `/validate` | POST | Validate a raw batch against schema |
| `/score` | POST | Validate + AI score a batch |
| `/gate/evaluate` | POST | Full pipeline: simulate → validate → score → gate |
| `/gate/history` | GET | Audit log of all gate decisions |
| `/gate/override` | POST | Human override of a REVIEW decision |

Docs available at `http://localhost:8000/docs` when the API server is running.

---

## UPI Schema Reference (NPCI UPI 2.0)

### Request

| Field | Type | Required | Constraint |
|---|---|---|---|
| `txnId` | string | Yes | Alphanumeric uppercase, max 35 chars |
| `msgId` | string | Yes | Alphanumeric uppercase, max 35 chars |
| `reqDate` | datetime | Yes | ISO-8601 |
| `txnType` | enum | Yes | Must be `BAL` |
| `orgId` | string | Yes | PSP org ID, 1–11 chars |
| `bankId` | string | Yes | Bank IIN/IFSC prefix, 4–11 chars |
| `vpa` | string | Yes | Format: `handle@bank` |
| `device.channel` | enum | Yes | `APP` / `WEB` / `USSD` / `SMS` / `IVRS` |
| `device.mobile` | string | Yes | Exactly 10 digits |
| `creds.hmac` | string | Yes | HMAC-SHA256 of credential data |

### Response

| Field | Type | Required on success | Constraint |
|---|---|---|---|
| `respCode` | enum | Yes | `00` / `ZM` / `91` / `YZ` / `ZS` / `AM` / `ZX` / `B3` |
| `balance` | decimal | Yes (`respCode=00`) | >= 0 |
| `ifsc` | string | Yes (`respCode=00`) | Format: `XXXX0XXXXXX` |
| `acType` | enum | Yes (`respCode=00`) | `SAVINGS` / `CURRENT` / `OD` / `CC` |
