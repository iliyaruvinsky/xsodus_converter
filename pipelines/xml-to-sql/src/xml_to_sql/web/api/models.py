"""Pydantic models for API requests and responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ConversionConfig(BaseModel):
    """Configuration for conversion."""

    database_mode: str = Field(default="hana", description="Target database (snowflake/hana)")
    hana_version: Optional[str] = Field(default="2.0", description="HANA version for HANA mode (1.0, 2.0, 2.0_SPS01, 2.0_SPS03)")
    hana_package: Optional[str] = Field(default=None, description="HANA package path (e.g., Macabi_BI.EYAL.EYAL_CDS)")
    target_schema: Optional[str] = Field(default="SAPABAP1", description="Target schema where tables reside (e.g., SAPABAP1)")
    client: str = Field(default="PROD", description="Default client value")
    language: str = Field(default="EN", description="Default language value")
    schema_overrides: Dict[str, str] = Field(default_factory=dict, description="Schema name overrides")
    view_schema: Optional[str] = Field(default="SAPABAP1", description="Schema where generated view should be created (SAPABAP1 for regular views, _SYS_BIC for calculation view references)")
    currency_udf_name: Optional[str] = Field(default=None, description="Currency conversion UDF name")
    currency_rates_table: Optional[str] = Field(default=None, description="Exchange rates table name")
    currency_schema: Optional[str] = Field(default=None, description="Schema for currency artifacts")
    auto_fix: bool = Field(default=False, description="Enable auto-correction of SQL issues")


class ConversionRequest(BaseModel):
    """Request model for single conversion."""

    config: ConversionConfig = Field(default_factory=ConversionConfig)


class WarningResponse(BaseModel):
    """Warning message model."""

    message: str
    level: str = "warning"  # 'warning' or 'error'


class ValidationIssue(BaseModel):
    """Validation issue model."""

    severity: str  # "error", "warning", "info"
    message: str
    code: str
    line_number: Optional[int] = None


class ValidationResult(BaseModel):
    """Validation result model."""

    is_valid: bool
    errors: List[ValidationIssue] = Field(default_factory=list)
    warnings: List[ValidationIssue] = Field(default_factory=list)
    info: List[ValidationIssue] = Field(default_factory=list)


class ConversionMetadata(BaseModel):
    """Metadata about the conversion."""

    scenario_id: Optional[str] = None
    nodes_count: int = 0
    filters_count: int = 0
    calculated_attributes_count: int = 0
    logical_model_present: bool = False


class BatchConversionRequest(BaseModel):
    """Request model for batch conversion."""

    config: ConversionConfig = Field(default_factory=ConversionConfig)


class BatchFileResult(BaseModel):
    """Result for a single file in batch conversion."""

    filename: str
    conversion_id: Optional[int] = None
    status: str  # 'success' or 'error'
    error_message: Optional[str] = None


class BatchConversionResponse(BaseModel):
    """Response model for batch conversion."""

    batch_id: str
    total_files: int
    successful: int
    failed: int
    results: List[BatchFileResult] = Field(default_factory=list)
    created_at: datetime


class HistoryEntry(BaseModel):
    """History entry for list view."""

    id: int
    filename: str
    scenario_id: Optional[str] = None
    status: str
    created_at: datetime
    file_size: Optional[int] = None
    error_message: Optional[str] = None


class HistoryListResponse(BaseModel):
    """Response model for history list."""

    entries: List[HistoryEntry]
    total: int
    page: int = 1
    page_size: int = 50


class ConversionStageInfo(BaseModel):
    """Information about a conversion stage."""
    
    stage_name: str
    status: str  # 'pending', 'in_progress', 'completed', 'failed'
    timestamp: Optional[datetime] = None
    duration_ms: Optional[int] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    xml_snippet: Optional[str] = None
    sql_snippet: Optional[str] = None
    error: Optional[str] = None


class CorrectionInfo(BaseModel):
    """Information about a single correction applied."""

    issue_code: str
    original_text: str
    corrected_text: str
    line_number: Optional[int] = None
    description: str = ""
    confidence: str  # "high", "medium", "low"


class CorrectionResult(BaseModel):
    """Result of auto-correction process."""

    corrected_sql: str
    corrections_applied: List[CorrectionInfo] = Field(default_factory=list)
    issues_fixed: List[str] = Field(default_factory=list)
    issues_remaining: List[ValidationIssue] = Field(default_factory=list)
    auto_fix_enabled: bool = False
    original_sql: str = ""


class ConversionResponse(BaseModel):
    """Response model for single conversion."""

    id: int
    filename: str
    scenario_id: Optional[str] = None
    sql_content: str
    abap_content: Optional[str] = None  # Generated ABAP Report program
    xml_content: Optional[str] = None  # Original XML file content
    warnings: List[WarningResponse] = Field(default_factory=list)
    metadata: Optional[ConversionMetadata] = None
    validation: Optional[ValidationResult] = None  # Validation results
    validation_logs: List[str] = Field(default_factory=list)
    corrections: Optional[CorrectionResult] = None  # Auto-correction results
    stages: List[ConversionStageInfo] = Field(default_factory=list)  # Conversion flow stages
    status: str = "success"
    error_message: Optional[str] = None
    created_at: datetime


class HistoryDetailResponse(BaseModel):
    """Response model for history detail."""

    id: int
    filename: str
    scenario_id: Optional[str] = None
    sql_content: str
    abap_content: Optional[str] = None  # Generated ABAP Report program
    xml_content: Optional[str] = None  # Original XML file content
    config_json: Optional[str] = None
    warnings: List[WarningResponse] = Field(default_factory=list)
    validation: Optional[ValidationResult] = None  # Validation results
    validation_logs: List[str] = Field(default_factory=list)
    corrections: Optional[CorrectionResult] = None  # Auto-correction results
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    file_size: Optional[int] = None

