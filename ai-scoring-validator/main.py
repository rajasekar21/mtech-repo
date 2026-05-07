"""
UPI Balance Enquiry Scoring Validator — main orchestrator.

Two operation modes:
  1. `python main.py simulate`   — one-shot simulation → validate → score → gate
  2. `python main.py serve`      — start FastAPI server (REST API mode)
  3. `python main.py kafka`      — consume Kafka stream continuously

Usage:
  python main.py simulate [--count 200] [--from staging] [--to production]
  python main.py serve
  python main.py kafka [--topic upi.balEnq.raw]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_simulate(count: int, from_env: str, to_env: str) -> None:
    from config.settings import settings
    from gate.deployment_gate import DeploymentGate, GateAuditLog
    from pipeline.apm_collector import APMCollector
    from scorer.ai_scorer import AIScorer
    from simulator.upi_simulator import UPISimulator
    from validator.schema_validator import SchemaValidator

    print("\n" + "=" * 60)
    print("  UPI Balance Enquiry Scoring Validator")
    print("=" * 60)

    # 1. Simulate
    print(f"\n[1/5] Generating {count} synthetic UPI Balance Enquiry transactions...")
    sim     = UPISimulator()
    records = sim.generate(count)
    valid_c   = sum(1 for r in records if r["profile"] == "valid")
    invalid_c = sum(1 for r in records if r["profile"] == "invalid")
    edge_c    = sum(1 for r in records if r["profile"] == "edge")
    print(f"      Generated: {count} total | {valid_c} valid | {invalid_c} invalid | {edge_c} edge")

    # 2. Validate
    print("\n[2/5] Validating against canonical UPI schema...")
    validator = SchemaValidator()
    summary   = validator.validate_batch(records)
    print(f"      Compliance: {summary.compliance_rate}%  "
          f"({summary.validCount}/{summary.totalRecords} passed)")
    if summary.top_errors:
        print("      Top field errors:")
        for e in summary.top_errors[:5]:
            print(f"        • {e['field']}: {e['count']} occurrences")

    # 3. APM
    print("\n[3/5] Collecting APM metrics...")
    apm_collector = APMCollector(prometheus_url=settings.PROMETHEUS_URL)
    apm = apm_collector.from_prometheus() or apm_collector.from_batch(summary)
    print(f"      Source: {apm.source}")
    if apm.latencyP99Ms:
        print(f"      Latency p99={apm.latencyP99Ms:.0f}ms  "
              f"errorRate={apm.errorRatePct:.1f}%  "
              f"tps={apm.tps:.1f}")

    # 4. AI scoring
    if not settings.ANTHROPIC_API_KEY:
        print("\n[4/5] AI Scoring — SKIPPED (ANTHROPIC_API_KEY not set)")
        print("      Set ANTHROPIC_API_KEY in environment to enable AI scoring.")
        print("\n[5/5] Gate decision — SKIPPED (no score available)")
        print("\n" + "=" * 60)
        return

    print("\n[4/5] Running AI scoring (Claude API)...")
    scorer  = AIScorer(api_key=settings.ANTHROPIC_API_KEY)
    scoring = scorer.score(summary, apm.to_dict())
    print(f"      Total score : {scoring.totalScore:.1f}/100")
    print(f"      Breakdown   : schema={scoring.schemaComplianceScore:.1f}  "
          f"quality={scoring.fieldQualityScore:.1f}  "
          f"anomaly={scoring.anomalyScore:.1f}  "
          f"apm={scoring.apmScore:.1f}")
    print(f"      Risk level  : {scoring.riskLevel}")
    print(f"      Rationale   : {scoring.rationale}")
    print(f"      Token usage : input={scoring.inputTokens} "
          f"output={scoring.outputTokens} "
          f"cacheRead={scoring.cacheReadTokens} "
          f"cacheWrite={scoring.cacheWriteTokens}")

    # 5. Gate decision
    print(f"\n[5/5] Deployment Gate: {from_env} → {to_env}")
    gate     = DeploymentGate(settings.PROMOTE_THRESHOLD, settings.REVIEW_THRESHOLD)
    decision = gate.evaluate(scoring, from_env=from_env, to_env=to_env)
    print(f"\n      {decision.summary_line()}")
    if scoring.recommendations:
        print("      Recommendations:")
        for rec in scoring.recommendations:
            print(f"        → {rec}")

    print("\n" + "=" * 60)
    print(json.dumps(decision.to_dict(), indent=2, default=str))
    print("=" * 60 + "\n")


def run_serve() -> None:
    import uvicorn
    from config.settings import settings
    print(f"Starting UPI Scoring Validator API on http://{settings.API_HOST}:{settings.API_PORT}")
    uvicorn.run(
        "api.server:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,
    )


def run_kafka(topic: str) -> None:
    from config.settings import settings
    from pipeline.apm_collector import APMCollector
    from pipeline.kafka_consumer import KafkaStreamConsumer
    from scorer.ai_scorer import AIScorer
    from gate.deployment_gate import DeploymentGate, GateAuditLog
    from validator.schema_validator import SchemaValidator

    validator = SchemaValidator()
    gate      = DeploymentGate(settings.PROMOTE_THRESHOLD, settings.REVIEW_THRESHOLD)
    audit     = GateAuditLog()
    apm_col   = APMCollector(prometheus_url=settings.PROMETHEUS_URL)

    consumer = KafkaStreamConsumer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        topic=topic or settings.KAFKA_TOPIC_RAW,
        group_id=settings.KAFKA_GROUP_ID,
        batch_size=settings.KAFKA_BATCH_SIZE,
        batch_timeout_s=settings.KAFKA_BATCH_TIMEOUT_S,
    )

    def process_batch(batch: list[dict]) -> None:
        logger.info("Processing Kafka batch of %d records", len(batch))
        summary  = validator.validate_batch(batch)
        apm      = apm_col.from_prometheus() or apm_col.from_batch(summary)

        if settings.ANTHROPIC_API_KEY:
            scorer   = AIScorer(api_key=settings.ANTHROPIC_API_KEY)
            scoring  = scorer.score(summary, apm.to_dict())
            decision = gate.evaluate(scoring)
            audit.record(decision)
            print(decision.summary_line())
        else:
            logger.warning("ANTHROPIC_API_KEY not set — validation only, no AI scoring")
            print(f"Validated {summary.totalRecords} records: {summary.compliance_rate}% compliant")

    print(f"Consuming from Kafka topic: {topic or settings.KAFKA_TOPIC_RAW}")
    print("Press Ctrl+C to stop.\n")
    consumer.start_background(on_batch=process_batch)
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        consumer.stop()
        print(f"\nStopped. Gate decisions this session: {audit.summary()['total']}")


# ─────────────────────────────────────────────
# CLI entrypoint
# ─────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="UPI Balance Enquiry Scoring Validator")
    sub    = parser.add_subparsers(dest="command")

    sim_p = sub.add_parser("simulate", help="Run one-shot simulation pipeline")
    sim_p.add_argument("--count",   type=int, default=100, help="Number of synthetic transactions")
    sim_p.add_argument("--from",    dest="from_env", default="staging")
    sim_p.add_argument("--to",      dest="to_env",   default="production")

    sub.add_parser("serve",  help="Start FastAPI REST server")

    kaf_p = sub.add_parser("kafka", help="Consume from Kafka topic continuously")
    kaf_p.add_argument("--topic", default=None)

    args = parser.parse_args()

    if args.command == "simulate":
        run_simulate(args.count, args.from_env, args.to_env)
    elif args.command == "serve":
        run_serve()
    elif args.command == "kafka":
        run_kafka(args.topic)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
