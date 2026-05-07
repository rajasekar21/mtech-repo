"""
Kafka stream consumer — primary ingestion source for UPI Balance Enquiry transactions.

Consumes from a configurable Kafka topic, deserialises transaction records,
and feeds them to the schema validator in configurable window batches.

Falls back gracefully to in-memory queue when Kafka is unavailable (useful for
local dev / simulator runs without a running broker).
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)


class InMemoryQueue:
    """Lightweight replacement for KafkaConsumer when no broker is available."""

    def __init__(self):
        self._q: queue.Queue = queue.Queue()

    def put(self, record: dict) -> None:
        self._q.put(record)

    def poll(self, timeout_ms: int = 1000, max_records: int = 500) -> list[dict]:
        records = []
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline and len(records) < max_records:
            try:
                records.append(self._q.get_nowait())
            except queue.Empty:
                time.sleep(0.05)
        return records

    def close(self):
        pass


class KafkaStreamConsumer:
    """
    Wraps kafka-python KafkaConsumer with windowed batch delivery.

    When Kafka is unavailable the consumer falls back to an InMemoryQueue
    so the rest of the pipeline continues working (e.g. with the simulator).
    """

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = "upi.balEnq.raw",
        group_id: str = "upi-scoring-validator",
        batch_size: int = 100,
        batch_timeout_s: int = 30,
        fallback_to_memory: bool = True,
    ):
        self._topic        = topic
        self._batch_size   = batch_size
        self._batch_timeout = batch_timeout_s
        self._consumer     = None
        self._memory_queue: InMemoryQueue | None = None
        self._running      = False
        self._thread: threading.Thread | None = None

        try:
            from kafka import KafkaConsumer  # type: ignore
            self._consumer = KafkaConsumer(
                topic,
                bootstrap_servers=bootstrap_servers,
                group_id=group_id,
                auto_offset_reset="latest",
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                consumer_timeout_ms=batch_timeout_s * 1000,
            )
            logger.info("Connected to Kafka broker at %s, topic=%s", bootstrap_servers, topic)
        except Exception as exc:
            if not fallback_to_memory:
                raise
            logger.warning(
                "Kafka unavailable (%s) — using in-memory queue fallback. "
                "Inject records via feed_record().",
                exc,
            )
            self._memory_queue = InMemoryQueue()

    # ── public ────────────────────────────────

    @property
    def using_kafka(self) -> bool:
        return self._consumer is not None

    def feed_record(self, record: dict) -> None:
        """Push a record into the in-memory fallback queue (used by simulator)."""
        if self._memory_queue is None:
            raise RuntimeError("In-memory queue not active; Kafka consumer is running.")
        self._memory_queue.put(record)

    def consume_batch(self) -> list[dict]:
        """
        Block until batch_size records arrive OR batch_timeout_s elapses.
        Returns whatever was collected.
        """
        if self._memory_queue:
            return self._memory_queue.poll(
                timeout_ms=self._batch_timeout * 1000,
                max_records=self._batch_size,
            )

        records: list[dict] = []
        deadline = time.monotonic() + self._batch_timeout
        for msg in self._consumer:
            records.append(msg.value)
            if len(records) >= self._batch_size:
                break
            if time.monotonic() >= deadline:
                break
        return records

    def start_background(self, on_batch: Callable[[list[dict]], None]) -> None:
        """
        Start consuming in a background thread.
        `on_batch` is called for each collected batch.
        """
        self._running = True

        def _loop():
            logger.info("Kafka consumer background loop started")
            while self._running:
                batch = self.consume_batch()
                if batch:
                    try:
                        on_batch(batch)
                    except Exception as exc:
                        logger.error("Error processing batch: %s", exc)
            logger.info("Kafka consumer background loop stopped")

        self._thread = threading.Thread(target=_loop, daemon=True, name="kafka-consumer")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        if self._consumer:
            self._consumer.close()
        logger.info("Kafka consumer stopped")
