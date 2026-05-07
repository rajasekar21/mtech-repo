"""
Centralised configuration — reads from environment variables with safe defaults.
"""

from __future__ import annotations

import os


class Settings:
    # Anthropic
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    KAFKA_TOPIC_RAW:         str = os.environ.get("KAFKA_TOPIC_RAW",         "upi.balEnq.raw")
    KAFKA_GROUP_ID:          str = os.environ.get("KAFKA_GROUP_ID",          "upi-scoring-validator")
    KAFKA_BATCH_SIZE:        int = int(os.environ.get("KAFKA_BATCH_SIZE",    "100"))
    KAFKA_BATCH_TIMEOUT_S:   int = int(os.environ.get("KAFKA_BATCH_TIMEOUT_S", "30"))

    # APM / Prometheus
    PROMETHEUS_URL: str | None = os.environ.get("PROMETHEUS_URL")

    # Scoring gate thresholds
    PROMOTE_THRESHOLD: float = float(os.environ.get("PROMOTE_THRESHOLD", "85"))
    REVIEW_THRESHOLD:  float = float(os.environ.get("REVIEW_THRESHOLD",  "70"))

    # Simulator defaults
    SIMULATOR_COUNT:    int  = int(os.environ.get("SIMULATOR_COUNT",    "100"))
    SIMULATOR_DELAY_MS: int  = int(os.environ.get("SIMULATOR_DELAY_MS", "0"))

    # Audit log
    AUDIT_LOG_PATH: str = os.environ.get("AUDIT_LOG_PATH", "./logs/audit.ndjson")

    # API server
    API_HOST: str = os.environ.get("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.environ.get("API_PORT", "8000"))

    # Environment labels
    FROM_ENV: str = os.environ.get("FROM_ENV", "staging")
    TO_ENV:   str = os.environ.get("TO_ENV",   "production")


settings = Settings()
