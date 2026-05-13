"""SQLite database setup — no server required."""
from __future__ import annotations

import json
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DB_PATH = "./data/api_intelligence.db"
engine  = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


class SpecRecord(Base):
    __tablename__ = "specs"
    id          = Column(String, primary_key=True)
    name        = Column(String, nullable=False)
    filename    = Column(String, nullable=False)
    page_count  = Column(Integer, default=0)
    api_count   = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=datetime.utcnow)


class ApiRecord(Base):
    __tablename__ = "apis"
    id              = Column(String, primary_key=True)
    spec_id         = Column(String, nullable=False, index=True)
    name            = Column(String, nullable=False)
    section         = Column(String)
    description     = Column(Text)
    request_fields  = Column(Text, default="[]")   # JSON
    response_fields = Column(Text, default="[]")   # JSON
    raw_text        = Column(Text, default="")

    def request_fields_list(self) -> list[dict]:
        return json.loads(self.request_fields or "[]")

    def response_fields_list(self) -> list[dict]:
        return json.loads(self.response_fields or "[]")


def init_db():
    import os
    os.makedirs("./data", exist_ok=True)
    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
