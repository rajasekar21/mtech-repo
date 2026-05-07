"""
UPI Balance Enquiry API schema — canonical template based on NPCI UPI 2.0 spec.
All live transactions are validated against these models.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ─────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────

class TxnType(str, Enum):
    BAL = "BAL"          # Balance Enquiry


class Channel(str, Enum):
    APP   = "APP"
    WEB   = "WEB"
    USSD  = "USSD"
    SMS   = "SMS"
    IVRS  = "IVRS"


class AccountType(str, Enum):
    SAVINGS = "SAVINGS"
    CURRENT = "CURRENT"
    OD      = "OD"
    CC      = "CC"


class RespCode(str, Enum):
    SUCCESS          = "00"
    INVALID_VPA      = "ZM"
    BANK_OFFLINE     = "91"
    TIMEOUT          = "YZ"
    DECRYPTION_ERROR = "ZS"
    INSUFFICIENT_BAL = "AM"
    SYSTEM_ERROR     = "ZX"
    DUPLICATE_TXN    = "B3"


# ─────────────────────────────────────────────
# Re-usable field patterns
# ─────────────────────────────────────────────

VPA_PATTERN     = re.compile(r"^[\w.\-]+@[\w]+$")
TXN_ID_PATTERN  = re.compile(r"^[A-Z0-9]{1,35}$")
MOBILE_PATTERN  = re.compile(r"^\d{10}$")
GEOCODE_PATTERN = re.compile(r"^-?\d{1,3}\.\d+,-?\d{1,3}\.\d+$")
IFSC_PATTERN    = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")


# ─────────────────────────────────────────────
# Sub-models
# ─────────────────────────────────────────────

class DeviceInfo(BaseModel):
    """Device fingerprint sent with every UPI request."""
    deviceId:   str = Field(..., min_length=1, max_length=64)
    channel:    Channel
    geocode:    Optional[str] = Field(None, description="lat,long")
    location:   Optional[str] = Field(None, max_length=255)
    ip:         Optional[str] = Field(None, max_length=45)
    mobile:     str           = Field(..., description="10-digit mobile number")
    os:         Optional[str] = Field(None, max_length=32)
    app:        Optional[str] = Field(None, max_length=64)
    capability: Optional[str] = Field(None, max_length=32)

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v: str) -> str:
        if not MOBILE_PATTERN.match(v):
            raise ValueError(f"Mobile must be 10 digits, got: {v!r}")
        return v

    @field_validator("geocode")
    @classmethod
    def validate_geocode(cls, v: Optional[str]) -> Optional[str]:
        if v and not GEOCODE_PATTERN.match(v):
            raise ValueError(f"Geocode must be 'lat,long' format, got: {v!r}")
        return v


class CredBlock(BaseModel):
    """Encrypted credential block (PIN/biometric)."""
    type:       str = Field(..., description="PIN/BIOMETRIC/OTP")
    subType:    str = Field(..., description="MPIN/IRIS/FACE")
    data:       str = Field(..., min_length=1, description="Base64-encoded encrypted credential")
    hmac:       str = Field(..., min_length=1, description="HMAC-SHA256 of data")


class AddInfo(BaseModel):
    """Additional info key-value pairs."""
    subMerchantId: Optional[str] = None
    merchantId:    Optional[str] = None
    initiationMode: Optional[str] = None
    purposeCode:    Optional[str] = None


# ─────────────────────────────────────────────
# Request schema
# ─────────────────────────────────────────────

class UPIBalEnqRequest(BaseModel):
    """
    UPI Balance Enquiry request — canonical NPCI schema template.
    Maps to BalEnq API (txnType=BAL).
    """
    txnId:   str        = Field(..., description="Unique transaction ID (UPI-generated)")
    msgId:   str        = Field(..., description="Message ID from PSP")
    reqDate: datetime   = Field(..., description="Request timestamp (ISO-8601)")
    txnType: TxnType    = Field(TxnType.BAL)
    orgId:   str        = Field(..., min_length=1, max_length=11, description="PSP org ID")
    bankId:  str        = Field(..., min_length=4,  max_length=11, description="Bank IIN/IFSC prefix")
    vpa:     str        = Field(..., description="Virtual Payment Address of account holder")
    device:  DeviceInfo
    creds:   CredBlock
    addInfo: Optional[AddInfo] = None

    @field_validator("txnId", "msgId")
    @classmethod
    def validate_txn_ids(cls, v: str) -> str:
        if not TXN_ID_PATTERN.match(v):
            raise ValueError(f"ID must be alphanumeric uppercase, max 35 chars: {v!r}")
        return v

    @field_validator("vpa")
    @classmethod
    def validate_vpa(cls, v: str) -> str:
        if not VPA_PATTERN.match(v):
            raise ValueError(f"Invalid VPA format (expected handle@bank): {v!r}")
        return v

    @model_validator(mode="after")
    def txn_type_must_be_bal(self) -> "UPIBalEnqRequest":
        if self.txnType != TxnType.BAL:
            raise ValueError("txnType must be BAL for Balance Enquiry requests")
        return self

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ─────────────────────────────────────────────
# Response schema
# ─────────────────────────────────────────────

class UPIBalEnqResponse(BaseModel):
    """
    UPI Balance Enquiry response — canonical NPCI schema template.
    """
    txnId:     str              = Field(..., description="Echoed from request")
    msgId:     str              = Field(..., description="Echoed from request")
    respCode:  RespCode         = Field(..., description="NPCI standard response code")
    respMsg:   str              = Field(..., max_length=255)
    timestamp: datetime         = Field(..., description="Response timestamp")
    accountNo: Optional[str]   = Field(None, description="Masked account number (last 4 visible)")
    ifsc:      Optional[str]   = Field(None, description="Bank IFSC code")
    bankName:  Optional[str]   = Field(None, max_length=100)
    acType:    Optional[AccountType] = None
    balance:   Optional[Decimal]     = Field(None, ge=Decimal("0"), description="Available balance in INR")
    acName:    Optional[str]         = Field(None, description="Masked account holder name")

    @field_validator("txnId", "msgId")
    @classmethod
    def validate_txn_ids(cls, v: str) -> str:
        if not TXN_ID_PATTERN.match(v):
            raise ValueError(f"ID must match request ID pattern: {v!r}")
        return v

    @field_validator("ifsc")
    @classmethod
    def validate_ifsc(cls, v: Optional[str]) -> Optional[str]:
        if v and not IFSC_PATTERN.match(v):
            raise ValueError(f"Invalid IFSC format: {v!r}")
        return v

    @model_validator(mode="after")
    def success_requires_balance_fields(self) -> "UPIBalEnqResponse":
        if self.respCode == RespCode.SUCCESS:
            missing = [f for f in ("accountNo", "ifsc", "bankName", "acType", "balance", "acName") if getattr(self, f) is None]
            if missing:
                raise ValueError(f"Successful response missing required fields: {missing}")
        return self

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), Decimal: str}


# ─────────────────────────────────────────────
# Paired transaction record (request + response)
# ─────────────────────────────────────────────

class UPIBalEnqTransaction(BaseModel):
    """A complete Balance Enquiry transaction — request/response pair."""
    request:      UPIBalEnqRequest
    response:     Optional[UPIBalEnqResponse] = None
    source:       str = Field("kafka", description="Data source: kafka | log | apm")
    receivedAt:   datetime = Field(default_factory=datetime.utcnow)
    latencyMs:    Optional[int] = Field(None, ge=0, description="End-to-end latency in ms")
