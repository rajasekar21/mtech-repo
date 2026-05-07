# AI Scoring Validator — UPI Balance Enquiry

AI-powered deployment gate that validates UPI Balance Enquiry API transactions
against the canonical NPCI schema, scores them using Claude AI, and decides
whether a build is ready to promote to the next environment.

## Architecture Diagram

[**View Architecture Diagram**](https://htmlpreview.github.io/?https://github.com/rajasekar21/mtech-repo/blob/claude/ai-scoring-validator-xN31p/ai-scoring-validator/architecture.html)

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
| **AI Scoring** | Claude claude-sonnet-4-6 | Scores batch 0–100 with prompt caching on the schema block |
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
│   └── ai_scorer.py              # Claude API scoring with prompt caching
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
├── architecture.html             # Interactive architecture diagram
├── docker-compose.yml            # Kafka + Prometheus + validator-api stack
├── Dockerfile
└── requirements.txt
```

---

## Quick Start

### Prerequisites

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
```

### 1. One-shot simulation (no Kafka needed)

```bash
python main.py simulate --count 200 --from staging --to production
```

Sample output:
```
[1/5] Generating 200 synthetic transactions...
[2/5] Validating against canonical UPI schema...   compliance: 82.0%
[3/5] Collecting APM metrics...                    source: computed
[4/5] Running AI scoring (Claude API)...           score: 87.5/100
[5/5] Deployment Gate: staging → production

      [PROMOTE] staging->production | score=87.5/100 risk=LOW
```

### 2. REST API server

```bash
python main.py serve
# API available at http://localhost:8000
# Docs at        http://localhost:8000/docs
```

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Liveness probe |
| `/simulate` | POST | Generate synthetic transactions |
| `/validate` | POST | Validate a raw batch against schema |
| `/score` | POST | Validate + AI score a batch |
| `/gate/evaluate` | POST | Full pipeline: simulate → validate → score → gate |
| `/gate/history` | GET | Audit log of all gate decisions |
| `/gate/override` | POST | Human override of a REVIEW decision |

### 3. Kafka stream mode

```bash
python main.py kafka --topic upi.balEnq.raw
```

### 4. Full Docker stack

```bash
ANTHROPIC_API_KEY=sk-ant-... docker-compose up
```

Services started:
- `localhost:9092` — Kafka broker
- `localhost:8080` — Kafka UI
- `localhost:9090` — Prometheus
- `localhost:8000` — Scoring Validator API

---

## Configuration

All settings are controlled via environment variables:

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(required)_ | Claude API key |
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
