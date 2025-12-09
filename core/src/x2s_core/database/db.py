"""Database connection and initialization."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

# SQLite database file location
# Check for environment variable, then try data directory, then project root
_db_path_env = os.getenv("DATABASE_PATH")
if _db_path_env:
    DB_PATH = Path(_db_path_env)
else:
    # Try data directory first (for Docker), then project root
    _data_dir = Path(__file__).parent.parent.parent.parent.parent / "data"
    if _data_dir.exists():
        DB_PATH = _data_dir / "conversions.db"
    else:
        DB_PATH = Path(__file__).parent.parent.parent.parent.parent / "conversions.db"

# Ensure parent directory exists
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    _ensure_additional_columns()


def _ensure_additional_columns() -> None:
    """Ensure new columns exist in legacy databases."""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    if "conversions" not in existing_tables:
        return

    existing_columns = {col["name"] for col in inspector.get_columns("conversions")}
    statements = []
    if "validation_result" not in existing_columns:
        statements.append("ALTER TABLE conversions ADD COLUMN validation_result TEXT")
    if "validation_logs" not in existing_columns:
        statements.append("ALTER TABLE conversions ADD COLUMN validation_logs TEXT")

    if statements:
        with engine.begin() as conn:
            for stmt in statements:
                conn.execute(text(stmt))


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

