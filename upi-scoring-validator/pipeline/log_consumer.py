"""
Log-based consumer — fallback/audit ingestion source.

Tails structured JSON log files (e.g. from a UPI middleware or API gateway)
and parses UPI Balance Enquiry records from them.

Used when Kafka is not available or for post-hoc validation of historical logs.
Supports both file-tail mode and log-directory-watch mode.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import time
from typing import Generator

logger = logging.getLogger(__name__)

# Lines that don't contain these strings are skipped quickly
_MUST_CONTAIN = ("txnType", "BAL", "vpa")


class LogConsumer:
    """
    Reads UPI transaction records from structured JSON log files.

    Expects one JSON object per line (NDJSON / JSON-L format), where each
    line is either a raw request/response dict or a simulator record.
    """

    def __init__(
        self,
        log_path: str,              # file or glob pattern, e.g. "/var/log/upi/*.log"
        follow: bool = False,       # tail -f behaviour
        poll_interval_s: float = 1.0,
    ):
        self._log_path      = log_path
        self._follow        = follow
        self._poll_interval = poll_interval_s

    def _iter_files(self) -> list[str]:
        paths = glob.glob(self._log_path)
        if not paths:
            logger.warning("No log files found matching pattern: %s", self._log_path)
        return sorted(paths)

    def _parse_line(self, line: str) -> dict | None:
        line = line.strip()
        if not line or not line.startswith("{"):
            return None
        if not any(k in line for k in _MUST_CONTAIN):
            return None
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None

    def read_batch(self, max_records: int = 500) -> list[dict]:
        """
        Read up to max_records from all matched log files.
        Non-blocking — returns immediately with whatever is available.
        """
        records: list[dict] = []
        for filepath in self._iter_files():
            try:
                with open(filepath, "r", encoding="utf-8") as fh:
                    for line in fh:
                        parsed = self._parse_line(line)
                        if parsed:
                            records.append(parsed)
                        if len(records) >= max_records:
                            return records
            except OSError as exc:
                logger.warning("Cannot read log file %s: %s", filepath, exc)
        return records

    def tail(self, max_records: int = 500) -> Generator[dict, None, None]:
        """
        Generator that tails log files (follow mode).
        Yields records as new lines are appended.
        Stops after max_records or when follow=False and EOF is reached.
        """
        for filepath in self._iter_files():
            try:
                with open(filepath, "r", encoding="utf-8") as fh:
                    # Seek to end for tail behaviour
                    if self._follow:
                        fh.seek(0, os.SEEK_END)
                    count = 0
                    while count < max_records:
                        line = fh.readline()
                        if line:
                            parsed = self._parse_line(line)
                            if parsed:
                                yield parsed
                                count += 1
                        else:
                            if not self._follow:
                                break
                            time.sleep(self._poll_interval)
            except OSError as exc:
                logger.warning("Cannot tail log file %s: %s", filepath, exc)


class LogWriter:
    """
    Appends validated transaction records to a structured JSON log file.
    Used as the audit trail sink — every record validated by the engine
    is written here regardless of validity.
    """

    def __init__(self, log_path: str):
        self._log_path = log_path
        os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)

    def write(self, record: dict) -> None:
        with open(self._log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

    def write_batch(self, records: list[dict]) -> None:
        with open(self._log_path, "a", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec) + "\n")
