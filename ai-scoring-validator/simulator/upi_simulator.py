"""
Synthetic UPI Balance Enquiry transaction simulator.

Generates realistic test transactions across four profiles:
  - valid:   well-formed, schema-compliant transactions
  - invalid: deliberately broken field values (schema violations)
  - edge:    boundary/corner cases (max-length fields, zero balance, etc.)
  - stress:  high-volume burst for load testing

Can publish directly to a Kafka topic or return transactions in-process.
"""

from __future__ import annotations

import json
import logging
import random
import string
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Generator

from schema.upi_balance_enquiry import (
    AccountType,
    AddInfo,
    Channel,
    CredBlock,
    DeviceInfo,
    RespCode,
    TxnType,
    UPIBalEnqRequest,
    UPIBalEnqResponse,
    UPIBalEnqTransaction,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Reference data pools
# ─────────────────────────────────────────────

BANKS = ["okaxis", "okhdfcbank", "okicici", "oksbi", "ybl", "upi", "paytm", "ibl"]
ORG_IDS = ["PYTM0000001", "AXTM0000002", "HDFC0000003", "SBIM0000004", "ICIC0000005"]
BANK_IDS = ["PYTM", "AXIS", "HDFC", "SBIN", "ICIC"]
OS_LIST = ["Android 13", "iOS 17.2", "Android 12", "iOS 16.5"]
APP_LIST = ["PhonePe/6.1", "GPay/143.0", "Paytm/9.8", "BHIM/2.6"]
NAMES = ["R****A K", "S****A P", "M****I R", "V****H S", "P****A T"]
GEOCODES = ["12.9716,77.5946", "19.0760,72.8777", "28.7041,77.1025", "13.0827,80.2707"]


def _rand_upper(length: int = 12) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def _rand_txn_id() -> str:
    return _rand_upper(random.randint(10, 35))


def _rand_vpa() -> str:
    handle = random.choice(["raj", "siva", "priya", "kumar", "anand", "devi"])
    suffix = random.choice(BANKS)
    return f"{handle}{random.randint(1, 9999)}@{suffix}"


def _rand_mobile() -> str:
    return f"9{random.randint(100000000, 999999999)}"


def _rand_account_no() -> str:
    return "XXXX" + str(random.randint(1000, 9999))


def _rand_ifsc() -> str:
    bank = random.choice(["HDFC", "SBIN", "ICIC", "AXIS", "PYTM"])
    return f"{bank}0{_rand_upper(6)}"


def _rand_balance() -> Decimal:
    return Decimal(str(round(random.uniform(0, 250000), 2)))


def _make_device(channel: Channel | None = None) -> DeviceInfo:
    return DeviceInfo(
        deviceId=str(uuid.uuid4()),
        channel=channel or random.choice(list(Channel)),
        geocode=random.choice(GEOCODES),
        location="India",
        ip=f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
        mobile=_rand_mobile(),
        os=random.choice(OS_LIST),
        app=random.choice(APP_LIST),
        capability="1234",
    )


def _make_creds() -> CredBlock:
    return CredBlock(
        type="PIN",
        subType="MPIN",
        data="Q29uZmlkZW50aWFsRW5jcnlwdGVkUElO",
        hmac="a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8",
    )


def _make_add_info() -> AddInfo:
    return AddInfo(initiationMode="00", purposeCode="00")


# ─────────────────────────────────────────────
# Request / Response builders
# ─────────────────────────────────────────────

def build_valid_request() -> UPIBalEnqRequest:
    return UPIBalEnqRequest(
        txnId=_rand_txn_id(),
        msgId=_rand_txn_id(),
        reqDate=datetime.now(timezone.utc),
        txnType=TxnType.BAL,
        orgId=random.choice(ORG_IDS),
        bankId=random.choice(BANK_IDS),
        vpa=_rand_vpa(),
        device=_make_device(),
        creds=_make_creds(),
        addInfo=_make_add_info(),
    )


def build_valid_response(req: UPIBalEnqRequest) -> UPIBalEnqResponse:
    return UPIBalEnqResponse(
        txnId=req.txnId,
        msgId=req.msgId,
        respCode=RespCode.SUCCESS,
        respMsg="Success",
        timestamp=datetime.now(timezone.utc),
        accountNo=_rand_account_no(),
        ifsc=_rand_ifsc(),
        bankName=random.choice(["HDFC Bank", "State Bank of India", "ICICI Bank", "Axis Bank"]),
        acType=random.choice(list(AccountType)),
        balance=_rand_balance(),
        acName=random.choice(NAMES),
    )


def build_invalid_request_raw() -> dict:
    """Returns a raw dict with deliberate schema violations (for negative testing)."""
    violation = random.choice([
        "bad_vpa",
        "bad_txn_id",
        "missing_required",
        "bad_mobile",
        "wrong_txn_type",
        "bad_geocode",
    ])

    base: dict = {
        "txnId": _rand_txn_id(),
        "msgId": _rand_txn_id(),
        "reqDate": datetime.now(timezone.utc).isoformat(),
        "txnType": "BAL",
        "orgId": random.choice(ORG_IDS),
        "bankId": random.choice(BANK_IDS),
        "vpa": _rand_vpa(),
        "device": {
            "deviceId": str(uuid.uuid4()),
            "channel": "APP",
            "geocode": random.choice(GEOCODES),
            "mobile": _rand_mobile(),
            "os": "Android 13",
            "app": "PhonePe/6.1",
            "capability": "1234",
        },
        "creds": {
            "type": "PIN",
            "subType": "MPIN",
            "data": "Q29uZmlkZW50aWFsRW5jcnlwdGVkUElO",
            "hmac": "a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8",
        },
        "_violation": violation,
    }

    if violation == "bad_vpa":
        base["vpa"] = "notavalid-vpa-format"
    elif violation == "bad_txn_id":
        base["txnId"] = "has spaces and $pecial chars!"
    elif violation == "missing_required":
        del base["orgId"]
    elif violation == "bad_mobile":
        base["device"]["mobile"] = "123"           # too short
    elif violation == "wrong_txn_type":
        base["txnType"] = "PAY"                    # not BAL
    elif violation == "bad_geocode":
        base["device"]["geocode"] = "not-a-coord"

    return base


def build_edge_request_raw() -> dict:
    """Returns raw dict for edge/boundary cases."""
    case = random.choice([
        "max_length_fields",
        "zero_balance_response",
        "future_timestamp",
        "unicode_vpa",
        "very_long_orgid",
    ])

    base: dict = {
        "txnId": _rand_upper(35),        # max length
        "msgId": _rand_upper(35),
        "reqDate": datetime.now(timezone.utc).isoformat(),
        "txnType": "BAL",
        "orgId": random.choice(ORG_IDS),
        "bankId": random.choice(BANK_IDS),
        "vpa": _rand_vpa(),
        "device": {
            "deviceId": "A" * 64,        # max length
            "channel": "APP",
            "geocode": "0.000000,0.000000",
            "mobile": _rand_mobile(),
            "os": "Android 13",
            "app": "PhonePe/6.1",
            "capability": "1234",
        },
        "creds": {
            "type": "PIN",
            "subType": "MPIN",
            "data": "Q29uZmlkZW50aWFsRW5jcnlwdGVkUElO",
            "hmac": "a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8",
        },
        "_edge_case": case,
    }

    if case == "future_timestamp":
        from datetime import timedelta
        base["reqDate"] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    elif case == "unicode_vpa":
        base["vpa"] = "test.user99@oksbi"   # dots allowed per spec
    elif case == "very_long_orgid":
        base["orgId"] = "TOOLONG12345"       # exceeds 11 chars
    elif case == "zero_balance_response":
        base["_zero_balance"] = True

    return base


# ─────────────────────────────────────────────
# Simulator class
# ─────────────────────────────────────────────

class UPISimulator:
    """
    Generates synthetic UPI Balance Enquiry transactions.

    profile_weights controls the mix:
      {"valid": 0.75, "invalid": 0.15, "edge": 0.10}
    """

    def __init__(
        self,
        profile_weights: dict[str, float] | None = None,
        kafka_producer=None,
        kafka_topic: str = "upi.balEnq.raw",
    ):
        self.weights = profile_weights or {"valid": 0.75, "invalid": 0.15, "edge": 0.10}
        self._kafka_producer = kafka_producer
        self._kafka_topic = kafka_topic

    # ── internal helpers ──────────────────────

    def _pick_profile(self) -> str:
        profiles = list(self.weights.keys())
        weights  = list(self.weights.values())
        return random.choices(profiles, weights=weights, k=1)[0]

    def _build_transaction(self) -> tuple[UPIBalEnqTransaction | None, dict | None, str]:
        """
        Returns (transaction, raw_invalid_dict, profile).
        One of the first two will be None.
        """
        profile = self._pick_profile()
        start = time.monotonic()

        if profile == "valid":
            req = build_valid_request()
            resp = build_valid_response(req)
            latency = int((time.monotonic() - start) * 1000) + random.randint(50, 800)
            txn = UPIBalEnqTransaction(
                request=req, response=resp, source="simulator", latencyMs=latency
            )
            return txn, None, profile

        elif profile == "invalid":
            raw = build_invalid_request_raw()
            return None, raw, profile

        else:  # edge
            raw = build_edge_request_raw()
            return None, raw, profile

    # ── public API ────────────────────────────

    def generate(self, count: int = 100) -> list[dict]:
        """
        Generate `count` synthetic transactions as dicts (ready for JSON / Kafka).
        Returns a list of records with 'profile', 'valid', and 'payload' keys.
        """
        records: list[dict] = []
        for _ in range(count):
            txn, raw, profile = self._build_transaction()
            if txn:
                records.append({
                    "profile": profile,
                    "valid": True,
                    "payload": json.loads(txn.model_dump_json()),
                })
            else:
                records.append({
                    "profile": profile,
                    "valid": False,
                    "payload": raw,
                })
        logger.info("Generated %d synthetic transactions", len(records))
        return records

    def stream(self, count: int = 100, delay_ms: int = 0) -> Generator[dict, None, None]:
        """Yield transactions one at a time — useful for streaming into Kafka or a pipeline."""
        for record in self.generate(count):
            if delay_ms:
                time.sleep(delay_ms / 1000)
            yield record

    def publish_to_kafka(self, count: int = 100) -> int:
        """
        Publish synthetic transactions to a Kafka topic.
        Requires a kafka-python KafkaProducer to be injected via constructor.
        Returns the number of messages published.
        """
        if not self._kafka_producer:
            raise RuntimeError("No KafkaProducer injected — use kafka_producer= in constructor")

        published = 0
        for record in self.stream(count):
            key = record["payload"].get("txnId") or record["payload"].get("request", {}).get("txnId", "")
            self._kafka_producer.send(
                self._kafka_topic,
                key=key.encode() if key else None,
                value=json.dumps(record).encode(),
            )
            published += 1

        self._kafka_producer.flush()
        logger.info("Published %d messages to Kafka topic %s", published, self._kafka_topic)
        return published
