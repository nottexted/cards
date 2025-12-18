from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

def utcnow() -> datetime:
    return datetime.utcnow()

def next_seq(db: Session, seq_name: str) -> int:
    return int(db.execute(text(f"SELECT nextval('{seq_name}')")).scalar_one())

def make_no(prefix: str, year: int, n: int, width: int = 6) -> str:
    return f"{prefix}-{year}-{n:0{width}d}"
