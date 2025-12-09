"""SQLAlchemy ORM models for conversion history."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, ForeignKey, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Conversion(Base):
    """Single XML to SQL conversion record."""

    __tablename__ = "conversions"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False, index=True)
    scenario_id = Column(String, nullable=True, index=True)
    sql_content = Column(Text, nullable=False)
    abap_content = Column(Text, nullable=True)  # Generated ABAP Report program
    xml_content = Column(Text, nullable=True)  # Original XML file content
    config_json = Column(Text, nullable=True)  # JSON string of config used
    warnings = Column(Text, nullable=True)  # JSON array of warnings
    validation_result = Column(Text, nullable=True)  # JSON serialized validation result
    validation_logs = Column(Text, nullable=True)  # JSON array of validation logs
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    file_size = Column(Integer, nullable=True)
    status = Column(String, default="success", nullable=False)  # 'success' or 'error'
    error_message = Column(Text, nullable=True)

    # Relationships
    batch_files = relationship("BatchFile", back_populates="conversion")


class BatchConversion(Base):
    """Batch conversion session record."""

    __tablename__ = "batch_conversions"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    total_files = Column(Integer, nullable=False, default=0)
    successful = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)

    # Relationships
    files = relationship("BatchFile", back_populates="batch")


class BatchFile(Base):
    """Link between batch conversion and individual conversions."""

    __tablename__ = "batch_files"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String, ForeignKey("batch_conversions.batch_id"), nullable=False, index=True)
    conversion_id = Column(Integer, ForeignKey("conversions.id"), nullable=False, index=True)
    filename = Column(String, nullable=False)

    # Relationships
    batch = relationship("BatchConversion", back_populates="files")
    conversion = relationship("Conversion", back_populates="batch_files")

