"""FastAPI routes for XML to SQL conversion."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import List
from zipfile import ZipFile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from ...web.database import get_db, Conversion, BatchConversion, BatchFile
from ...web.services.converter import convert_xml_to_sql, ConversionResult
from ...web.services.xml_utils import prettify_xml
from ...package_mapper import get_package
from ...package_mapping_db import PackageMappingDB
from .models import (
    ConversionConfig,
    ConversionRequest,
    ConversionResponse,
    WarningResponse,
    ConversionMetadata,
    ValidationIssue,
    ValidationResult,
    ConversionStageInfo,
    CorrectionInfo,
    CorrectionResult as CorrectionResultModel,
    BatchConversionRequest,
    BatchConversionResponse,
    BatchFileResult,
    HistoryEntry,
    HistoryListResponse,
    HistoryDetailResponse,
)

router = APIRouter(prefix="/api", tags=["conversion"])


def write_latest_sql_to_file(sql_content: str, scenario_id: str) -> None:
    """Write generated SQL to LATEST_SQL_FROM_DB.txt for testing automation.

    Saves to xsodus_converter/ root for easy access during testing.
    Path: routes.py is in xsodus_converter/pipelines/xml-to-sql/src/xml_to_sql/web/api/
    7 levels up gets to xsodus_converter folder.
    """
    try:
        # 7 levels up: routes.py->api->web->xml_to_sql->src->xml-to-sql->pipelines->xsodus_converter
        repo_root = Path(__file__).parent.parent.parent.parent.parent.parent.parent
        latest_sql_file = repo_root / "LATEST_SQL_FROM_DB.txt"

        # Write SQL with scenario_id comment
        with open(latest_sql_file, "w", encoding="utf-8") as f:
            f.write(f"-- Last generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- Scenario ID: {scenario_id}\n\n")
            f.write(sql_content)
        print(f"SQL saved to: {latest_sql_file}")
    except Exception as e:
        # Don't fail the conversion if file write fails
        print(f"Warning: Failed to write LATEST_SQL_FROM_DB.txt: {e}")


# NOTE: More specific routes must come BEFORE less specific ones in FastAPI
# So /convert/single/stream must be defined before /convert/single

@router.post("/convert/single/stream")
async def convert_single_stream(
    file: UploadFile = File(..., description="XML file to convert"),
    config_json: str = Form(default="{}", description="Configuration as JSON string"),
    db: Session = Depends(get_db),
):
    """Convert a single XML file to SQL with real-time progress streaming via SSE."""
    from .sse_helper import format_sse_message, stage_to_sse_dict

    # Validate file type
    if not file.filename or not file.filename.lower().endswith((".xml", ".XML")):
        raise HTTPException(status_code=400, detail="File must be an XML file")

    # Parse configuration
    try:
        config = ConversionConfig(**json.loads(config_json))
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")

    # Read file content
    xml_content_bytes = await file.read()

    # Auto-detect package if not provided and database mode is HANA
    hana_package = config.hana_package
    if not hana_package and config.database_mode.lower() == "hana" and file.filename:
        cv_name = Path(file.filename).stem
        auto_package = get_package(cv_name)
        if auto_package:
            hana_package = auto_package

    async def event_generator():
        """Generate SSE events as conversion progresses."""
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        try:
            # Start conversion message
            yield format_sse_message("start", {"filename": file.filename})

            # Track stages for streaming
            streamed_stages = []

            def progress_callback(stage):
                """Capture and stream stage updates."""
                stage_dict = stage_to_sse_dict(stage)
                streamed_stages.append(stage_dict)

            # Run the synchronous conversion in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(
                    executor,
                    lambda: convert_xml_to_sql(
                        xml_content=xml_content_bytes,
                        database_mode=config.database_mode,
                        hana_version=config.hana_version,
                        hana_package=hana_package,
                        target_schema=config.target_schema,
                        client=config.client,
                        language=config.language,
                        schema_overrides=config.schema_overrides,
                        view_schema=config.view_schema,
                        currency_udf_name=config.currency_udf_name,
                        currency_rates_table=config.currency_rates_table,
                        currency_schema=config.currency_schema,
                        auto_fix=config.auto_fix,
                        on_stage_update=progress_callback,
                    )
                )

            # Stream all stages that were captured
            for stage in streamed_stages:
                yield format_sse_message("stage_update", stage)

            # Send completion event with full result
            if result.error:
                yield format_sse_message("error", {
                    "error": result.error,
                    "scenario_id": result.scenario_id
                })
            else:
                # Save to database
                conversion = Conversion(
                    filename=file.filename,
                    scenario_id=result.scenario_id,
                    xml_content=xml_content_bytes.decode('utf-8', errors='ignore'),
                    sql_content=result.sql_content or "",
                    abap_content=result.abap_content,
                    status="success",
                    database_mode=config.database_mode,
                    created_at=datetime.now(),
                )
                db.add(conversion)
                db.commit()
                db.refresh(conversion)

                # Write SQL to LATEST_SQL_FROM_DB.txt for Claude Code analysis
                write_latest_sql_to_file(result.sql_content, result.scenario_id)

                yield format_sse_message("complete", {
                    "conversion_id": conversion.id,
                    "scenario_id": result.scenario_id,
                    "sql_content": result.sql_content,
                    "abap_content": result.abap_content,
                    "warnings": [w.message for w in result.warnings] if result.warnings else [],
                })

        except Exception as e:
            yield format_sse_message("error", {"error": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/convert/single", response_model=ConversionResponse)
async def convert_single(
    file: UploadFile = File(..., description="XML file to convert"),
    config_json: str = Form(default="{}", description="Configuration as JSON string"),
    db: Session = Depends(get_db),
) -> ConversionResponse:
    """Convert a single XML file to SQL."""
    
    # Validate file type
    if not file.filename or not file.filename.lower().endswith((".xml", ".XML")):
        raise HTTPException(status_code=400, detail="File must be an XML file")
    
    # Parse configuration
    try:
        config_dict = json.loads(config_json) if config_json else {}
        config = ConversionConfig(**config_dict)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in config_json")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    
    # Read file content
    try:
        xml_content_bytes = await file.read()
        file_size = len(xml_content_bytes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")
    
    # Format XML for storage
    xml_content_formatted = prettify_xml(xml_content_bytes)

    # Auto-detect package if not provided and database mode is HANA
    hana_package = config.hana_package
    if not hana_package and config.database_mode.lower() == "hana" and file.filename:
        cv_name = Path(file.filename).stem
        auto_package = get_package(cv_name)
        if auto_package:
            hana_package = auto_package

    # Convert XML to SQL
    result = convert_xml_to_sql(
        xml_content=xml_content_bytes,
        database_mode=config.database_mode,
        hana_version=config.hana_version,
        hana_package=hana_package,
        target_schema=config.target_schema,
        client=config.client,
        language=config.language,
        schema_overrides=config.schema_overrides,
        view_schema=config.view_schema,
        currency_udf_name=config.currency_udf_name,
        currency_rates_table=config.currency_rates_table,
        currency_schema=config.currency_schema,
        auto_fix=config.auto_fix,
    )
    
    if result.error:
        # Save error to database
        conversion = Conversion(
            filename=file.filename or "unknown.xml",
            scenario_id=result.scenario_id,
            sql_content="",
            xml_content=xml_content_formatted,
            config_json=config_json,
            warnings=json.dumps([]),
            validation_result=None,
            validation_logs=json.dumps(result.validation_logs or []),
            file_size=file_size,
            status="error",
            error_message=result.error,
        )
        db.add(conversion)
        db.commit()
        db.refresh(conversion)
        
        raise HTTPException(status_code=500, detail=result.error)
    
    warnings = [WarningResponse(message=w, level="warning") for w in result.warnings]
    metadata = ConversionMetadata(**result.metadata) if result.metadata else None

    # Convert validation result to API model
    validation = None
    if result.validation:
        validation = ValidationResult(
            is_valid=result.validation.is_valid,
            errors=[
                ValidationIssue(
                    severity=issue.severity.value,
                    message=issue.message,
                    code=issue.code,
                    line_number=issue.line_number,
                )
                for issue in result.validation.errors
            ],
            warnings=[
                ValidationIssue(
                    severity=issue.severity.value,
                    message=issue.message,
                    code=issue.code,
                    line_number=issue.line_number,
                )
                for issue in result.validation.warnings
            ],
            info=[
                ValidationIssue(
                    severity=issue.severity.value,
                    message=issue.message,
                    code=issue.code,
                    line_number=issue.line_number,
                )
                for issue in result.validation.info
            ],
        )
    
    # Convert correction result to API model
    corrections = None
    if result.corrections:
        from ...sql.corrector import CorrectionResult
        corrections = CorrectionResultModel(
            corrected_sql=result.corrections.corrected_sql,
            corrections_applied=[
                CorrectionInfo(
                    issue_code=c.issue_code,
                    original_text=c.original_text,
                    corrected_text=c.corrected_text,
                    line_number=c.line_number,
                    description=c.description,
                    confidence=c.confidence.value,
                )
                for c in result.corrections.corrections_applied
            ],
            issues_fixed=result.corrections.issues_fixed,
            issues_remaining=[
                ValidationIssue(
                    severity=issue.severity.value,
                    message=issue.message,
                    code=issue.code,
                    line_number=issue.line_number,
                )
                for issue in result.corrections.issues_remaining
            ],
            auto_fix_enabled=result.corrections.auto_fix_enabled,
            original_sql=result.corrections.original_sql,
        )
    
    # Convert stages to API model
    stages = [
        ConversionStageInfo(
            stage_name=stage.stage_name,
            status=stage.status,
            timestamp=stage.timestamp,
            duration_ms=stage.duration_ms,
            details=stage.details,
            xml_snippet=stage.xml_snippet,
            sql_snippet=stage.sql_snippet,
            error=stage.error,
        )
        for stage in result.stages
    ]
    
    # Save to database
    conversion = Conversion(
        filename=file.filename or "unknown.xml",
        scenario_id=result.scenario_id,
        sql_content=result.sql_content,
        abap_content=result.abap_content,
        xml_content=xml_content_formatted,
        config_json=config_json,
        warnings=json.dumps([w for w in result.warnings]),
        validation_result=validation.json() if validation else None,
        validation_logs=json.dumps(result.validation_logs or []),
        file_size=file_size,
        status="success",
    )
    db.add(conversion)
    db.commit()
    db.refresh(conversion)

    # Write SQL to LATEST_SQL_FROM_DB.txt for Claude Code analysis
    write_latest_sql_to_file(result.sql_content, result.scenario_id)

    return ConversionResponse(
        id=conversion.id,
        filename=conversion.filename,
        scenario_id=conversion.scenario_id,
        sql_content=conversion.sql_content,
        abap_content=conversion.abap_content,
        xml_content=conversion.xml_content,
        warnings=warnings,
        metadata=metadata,
        validation=validation,
        validation_logs=result.validation_logs or [],
        corrections=corrections,
        stages=stages,
        status=conversion.status,
        error_message=conversion.error_message,
        created_at=conversion.created_at,
    )


@router.post("/convert/batch", response_model=BatchConversionResponse)
async def convert_batch(
    files: List[UploadFile] = File(..., description="XML files to convert"),
    config_json: str = Form(default="{}", description="Configuration as JSON string"),
    db: Session = Depends(get_db),
) -> BatchConversionResponse:
    """Convert multiple XML files to SQL."""
    
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")
    
    # Parse configuration
    try:
        config_dict = json.loads(config_json) if config_json else {}
        config = ConversionConfig(**config_dict)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in config_json")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    
    # Create batch record
    batch_id = str(uuid.uuid4())
    batch = BatchConversion(
        batch_id=batch_id,
        total_files=len(files),
        successful=0,
        failed=0,
    )
    db.add(batch)
    db.commit()
    
    results: List[BatchFileResult] = []
    
    # Process each file
    for file in files:
        if not file.filename or not file.filename.lower().endswith((".xml", ".XML")):
            results.append(BatchFileResult(
                filename=file.filename or "unknown.xml",
                status="error",
                error_message="File must be an XML file",
            ))
            batch.failed += 1
            continue
        
        try:
            xml_content_bytes = await file.read()
            file_size = len(xml_content_bytes)
        except Exception as e:
            results.append(BatchFileResult(
                filename=file.filename or "unknown.xml",
                status="error",
                error_message=f"Error reading file: {str(e)}",
            ))
            batch.failed += 1
            continue
        
        # Format XML for storage
        xml_content_formatted = prettify_xml(xml_content_bytes)

        # Auto-detect package if not provided and database mode is HANA
        hana_package = config.hana_package
        if not hana_package and config.database_mode.lower() == "hana" and file.filename:
            cv_name = Path(file.filename).stem
            auto_package = get_package(cv_name)
            if auto_package:
                hana_package = auto_package

        # Convert XML to SQL
        result = convert_xml_to_sql(
            xml_content=xml_content_bytes,
            database_mode=config.database_mode,
            hana_version=config.hana_version,
            hana_package=hana_package,
            target_schema=config.target_schema,
            client=config.client,
            language=config.language,
            schema_overrides=config.schema_overrides,
            view_schema=config.view_schema,
            currency_udf_name=config.currency_udf_name,
            currency_rates_table=config.currency_rates_table,
            currency_schema=config.currency_schema,
            auto_fix=config.auto_fix,
        )

        if result.error:
            conversion = Conversion(
                filename=file.filename or "unknown.xml",
                scenario_id=result.scenario_id,
                sql_content="",
                xml_content=xml_content_formatted,
                config_json=config_json,
                warnings=json.dumps([]),
                file_size=file_size,
                status="error",
                error_message=result.error,
            )
            db.add(conversion)
            db.commit()
            db.refresh(conversion)
            
            # Link to batch
            batch_file = BatchFile(
                batch_id=batch_id,
                conversion_id=conversion.id,
                filename=file.filename or "unknown.xml",
            )
            db.add(batch_file)
            
            results.append(BatchFileResult(
                filename=file.filename or "unknown.xml",
                conversion_id=conversion.id,
                status="error",
                error_message=result.error,
            ))
            batch.failed += 1
        else:
            # Save successful conversion
            conversion = Conversion(
                filename=file.filename or "unknown.xml",
                scenario_id=result.scenario_id,
                sql_content=result.sql_content,
                abap_content=result.abap_content,
                xml_content=xml_content_formatted,
                config_json=config_json,
                warnings=json.dumps([w for w in result.warnings]),
                file_size=file_size,
                status="success",
            )
            db.add(conversion)
            db.commit()
            db.refresh(conversion)

            # Write SQL to LATEST_SQL_FROM_DB.txt for Claude Code analysis
            write_latest_sql_to_file(result.sql_content, result.scenario_id)

            # Link to batch
            batch_file = BatchFile(
                batch_id=batch_id,
                conversion_id=conversion.id,
                filename=file.filename or "unknown.xml",
            )
            db.add(batch_file)
            
            results.append(BatchFileResult(
                filename=file.filename or "unknown.xml",
                conversion_id=conversion.id,
                status="success",
            ))
            batch.successful += 1
    
    db.commit()
    db.refresh(batch)
    
    return BatchConversionResponse(
        batch_id=batch.batch_id,
        total_files=batch.total_files,
        successful=batch.successful,
        failed=batch.failed,
        results=results,
        created_at=batch.created_at,
    )


@router.get("/download/{conversion_id}")
async def download_sql(
    conversion_id: int,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Download SQL file for a conversion."""

    conversion = db.query(Conversion).filter(Conversion.id == conversion_id).first()
    if not conversion:
        raise HTTPException(status_code=404, detail="Conversion not found")

    if conversion.status != "success":
        raise HTTPException(status_code=400, detail="Conversion was not successful")

    # Generate filename
    filename = conversion.filename.rsplit(".", 1)[0] + ".sql" if "." in conversion.filename else conversion.filename + ".sql"

    return StreamingResponse(
        BytesIO(conversion.sql_content.encode("utf-8")),
        media_type="application/sql",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/generate-abap/{conversion_id}")
async def generate_abap(
    conversion_id: int,
    mode: str = Query(default="pure", description="ABAP generation mode: 'pure' (portable) or 'exec_sql' (HANA only)"),
    db: Session = Depends(get_db),
) -> dict:
    """Generate ABAP Report for a conversion on demand.

    Two modes available:
    - pure: Uses native SELECT statements with FOR ALL ENTRIES. Works on ANY SAP system.
    - exec_sql: Uses EXEC SQL/ENDEXEC blocks. HANA only, but supports CV references.
    """
    conversion = db.query(Conversion).filter(Conversion.id == conversion_id).first()
    if not conversion:
        raise HTTPException(status_code=404, detail="Conversion not found")

    if conversion.status != "success":
        raise HTTPException(status_code=400, detail="Conversion was not successful")

    if not conversion.sql_content:
        raise HTTPException(status_code=400, detail="No SQL content available for ABAP generation")

    # Validate mode parameter
    if mode not in ("pure", "exec_sql"):
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'pure' or 'exec_sql'")

    try:
        if mode == "pure":
            # Pure ABAP mode (portable, no EXEC SQL)
            from ...abap import generate_pure_abap_from_sql
            abap_content = generate_pure_abap_from_sql(
                sql=conversion.sql_content,
                scenario_id=conversion.scenario_id or "GENERATED_VIEW",
            )
            program_name = f"Z_PURE_{conversion.scenario_id}".upper()[:30] if conversion.scenario_id else "Z_PURE_EXPORT"
        else:
            # EXEC SQL mode (HANA only)
            from ...abap import generate_abap_report
            abap_content = generate_abap_report(
                sql_content=conversion.sql_content,
                scenario_id=conversion.scenario_id or "GENERATED_VIEW",
            )
            program_name = f"Z_XDS_{conversion.scenario_id}".upper()[:30] if conversion.scenario_id else "Z_XDS_EXPORT"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ABAP generation failed: {str(e)}")

    # Save to database
    conversion.abap_content = abap_content
    db.commit()

    return {
        "success": True,
        "conversion_id": conversion_id,
        "abap_content": abap_content,
        "program_name": program_name,
        "mode": mode,
    }


@router.get("/download/{conversion_id}/abap")
async def download_abap(
    conversion_id: int,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Download ABAP Report file for a conversion."""

    conversion = db.query(Conversion).filter(Conversion.id == conversion_id).first()
    if not conversion:
        raise HTTPException(status_code=404, detail="Conversion not found")

    if conversion.status != "success":
        raise HTTPException(status_code=400, detail="Conversion was not successful")

    if not conversion.abap_content:
        raise HTTPException(status_code=404, detail="ABAP content not available for this conversion. Generate it first.")

    # Generate filename - ABAP programs use .abap extension
    base_name = conversion.filename.rsplit(".", 1)[0] if "." in conversion.filename else conversion.filename
    filename = f"Z_XDS_{base_name}.abap".upper()

    return StreamingResponse(
        BytesIO(conversion.abap_content.encode("utf-8")),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/download/batch/{batch_id}")
async def download_batch_zip(
    batch_id: str,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Download all SQL files from a batch as a ZIP."""
    
    batch = db.query(BatchConversion).filter(BatchConversion.batch_id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Get all successful conversions for this batch
    batch_files = db.query(BatchFile).filter(
        BatchFile.batch_id == batch_id
    ).all()
    
    conversions = [
        db.query(Conversion).filter(Conversion.id == bf.conversion_id).first()
        for bf in batch_files
    ]
    conversions = [c for c in conversions if c and c.status == "success"]
    
    if not conversions:
        raise HTTPException(status_code=404, detail="No successful conversions found in batch")
    
    # Create ZIP in memory
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w") as zip_file:
        for conversion in conversions:
            filename = conversion.filename.rsplit(".", 1)[0] + ".sql" if "." in conversion.filename else conversion.filename + ".sql"
            zip_file.writestr(filename, conversion.sql_content.encode("utf-8"))
    
    zip_buffer.seek(0)
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="batch_{batch_id}.zip"'},
    )


@router.get("/history", response_model=HistoryListResponse)
async def get_history(
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
) -> HistoryListResponse:
    """Get conversion history with pagination."""
    
    offset = (page - 1) * page_size
    
    # Get total count
    total = db.query(Conversion).count()
    
    # Get paginated entries
    conversions = db.query(Conversion).order_by(Conversion.created_at.desc()).offset(offset).limit(page_size).all()
    
    entries = [
        HistoryEntry(
            id=c.id,
            filename=c.filename,
            scenario_id=c.scenario_id,
            status=c.status,
            created_at=c.created_at,
            file_size=c.file_size,
            error_message=c.error_message,
        )
        for c in conversions
    ]
    
    return HistoryListResponse(
        entries=entries,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/history/{conversion_id}", response_model=HistoryDetailResponse)
async def get_history_detail(
    conversion_id: int,
    db: Session = Depends(get_db),
) -> HistoryDetailResponse:
    """Get detailed information about a conversion."""
    
    conversion = db.query(Conversion).filter(Conversion.id == conversion_id).first()
    if not conversion:
        raise HTTPException(status_code=404, detail="Conversion not found")
    
    warnings = []
    if conversion.warnings:
        try:
            warnings_data = json.loads(conversion.warnings)
            warnings = [WarningResponse(message=w, level="warning") for w in warnings_data]
        except (json.JSONDecodeError, TypeError):
            pass

    validation = None
    if conversion.validation_result:
        try:
            validation_data = json.loads(conversion.validation_result)
            validation = ValidationResult(**validation_data)
        except (json.JSONDecodeError, TypeError, ValueError):
            validation = None

    validation_logs: list[str] = []
    if conversion.validation_logs:
        try:
            logs_data = json.loads(conversion.validation_logs)
            if isinstance(logs_data, list):
                validation_logs = [str(item) for item in logs_data]
        except (json.JSONDecodeError, TypeError, ValueError):
            validation_logs = []
    
    return HistoryDetailResponse(
        id=conversion.id,
        filename=conversion.filename,
        scenario_id=conversion.scenario_id,
        sql_content=conversion.sql_content,
        abap_content=conversion.abap_content,
        xml_content=conversion.xml_content,
        config_json=conversion.config_json,
        warnings=warnings,
        validation=validation,
        validation_logs=validation_logs,
        status=conversion.status,
        error_message=conversion.error_message,
        created_at=conversion.created_at,
        file_size=conversion.file_size,
    )


@router.delete("/history/{conversion_id}")
async def delete_history(
    conversion_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Delete a conversion from history."""
    
    conversion = db.query(Conversion).filter(Conversion.id == conversion_id).first()
    if not conversion:
        raise HTTPException(status_code=404, detail="Conversion not found")
    
    # Delete associated batch file links
    db.query(BatchFile).filter(BatchFile.conversion_id == conversion_id).delete()
    
    # Delete conversion
    db.delete(conversion)
    db.commit()
    
    return {"message": "Conversion deleted successfully"}


@router.delete("/history")
async def delete_history_bulk(
    ids: str | None = Query(
        default=None,
        description="Comma-separated list of conversion IDs to delete. If omitted, all history will be deleted.",
    ),
    db: Session = Depends(get_db),
) -> dict:
    """Delete multiple conversions or all history."""

    if ids:
        try:
            id_list = [int(item.strip()) for item in ids.split(",") if item.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversion ID list")

        if not id_list:
            raise HTTPException(status_code=400, detail="No valid conversion IDs provided")

        # Delete associated batch links first
        db.query(BatchFile).filter(BatchFile.conversion_id.in_(id_list)).delete(
            synchronize_session=False
        )

        deleted = db.query(Conversion).filter(Conversion.id.in_(id_list)).delete(
            synchronize_session=False
        )
        db.commit()

        return {"message": "Selected conversions deleted successfully", "deleted": deleted}

    # Delete entire history
    db.query(BatchFile).delete()
    deleted = db.query(Conversion).delete()
    db.commit()

    return {"message": "All conversion history deleted successfully", "deleted": deleted}


# Package Mapping Endpoints

@router.post("/package-mappings/upload")
async def upload_package_mapping(
    file: UploadFile = File(..., description="Excel file with package mappings"),
    instance_name: str = Form(None, description="HANA instance name (auto-detected from filename if not provided)"),
    instance_type: str = Form(None, description="Instance type (ECC, BW, S4HANA, etc.)"),
) -> dict:
    """Upload and import package mapping Excel file."""

    # Validate file type
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="File must be an Excel file (.xlsx or .xls)")

    try:
        # Auto-detect instance name from filename if not provided
        if not instance_name:
            # Expected format: HANA_CV_MBD.xlsx → "MBD (ECC)"
            import re
            match = re.match(r'HANA_CV_(\w+)\.xlsx?', file.filename, re.IGNORECASE)
            if match:
                code = match.group(1)
                instance_name = f"{code} (ECC)"  # Default to ECC if type not provided
            else:
                instance_name = Path(file.filename).stem  # Use filename without extension

        # Save uploaded file to uploads folder
        project_root = Path(__file__).parent.parent.parent.parent.parent
        uploads_dir = project_root / "package_mappings" / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)

        file_path = uploads_dir / file.filename

        # Write file to disk
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Import into database
        db = PackageMappingDB()
        result = db.import_from_excel(file_path, instance_name, instance_type)

        if result["status"] == "SUCCESS":
            # Move to processed folder (use replace() to overwrite existing files on re-upload)
            processed_dir = project_root / "package_mappings" / "processed"
            processed_dir.mkdir(parents=True, exist_ok=True)

            processed_path = processed_dir / file.filename
            file_path.replace(processed_path)  # replace() overwrites existing files

            return {
                "status": "success",
                "message": f"Successfully imported {result['cv_count']} CVs for instance '{instance_name}'",
                "instance_name": instance_name,
                "instance_id": result["instance_id"],
                "cv_count": result["cv_count"],
                "source_file": file.filename
            }
        else:
            # Move to failed folder (use replace() to overwrite existing files on re-upload)
            failed_dir = project_root / "package_mappings" / "failed"
            failed_dir.mkdir(parents=True, exist_ok=True)

            failed_path = failed_dir / file.filename
            file_path.replace(failed_path)  # replace() overwrites existing files

            raise HTTPException(
                status_code=500,
                detail=f"Failed to import mappings: {result.get('error', 'Unknown error')}"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/package-mappings/instances")
async def get_instances() -> dict:
    """Get list of all HANA instances with package mappings."""

    try:
        db = PackageMappingDB()
        instances = db.get_instances()

        return {
            "instances": instances,
            "total": len(instances)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get instances: {str(e)}")


@router.get("/package-mappings/instance/{instance_id}")
async def get_instance_details(instance_id: int) -> dict:
    """Get detailed information about a specific instance."""

    try:
        db = PackageMappingDB()

        # Get instance info
        instances = db.get_instances()
        instance = next((i for i in instances if i["instance_id"] == instance_id), None)

        if not instance:
            raise HTTPException(status_code=404, detail="Instance not found")

        # Get statistics for this instance
        import sqlite3
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()

            # Get CV count
            cursor.execute("""
                SELECT COUNT(*) FROM package_mappings
                WHERE instance_id = ? AND is_active = 1
            """, (instance_id,))
            cv_count = cursor.fetchone()[0]

            # Get unique packages count
            cursor.execute("""
                SELECT COUNT(DISTINCT package_path) FROM package_mappings
                WHERE instance_id = ? AND is_active = 1
            """, (instance_id,))
            package_count = cursor.fetchone()[0]

            # Get top packages
            cursor.execute("""
                SELECT package_path, COUNT(*) as cv_count
                FROM package_mappings
                WHERE instance_id = ? AND is_active = 1
                GROUP BY package_path
                ORDER BY cv_count DESC
                LIMIT 10
            """, (instance_id,))
            top_packages = [{"package": row[0], "cv_count": row[1]} for row in cursor.fetchall()]

            # Get recent CVs
            cursor.execute("""
                SELECT cv_name, package_path, import_date
                FROM package_mappings
                WHERE instance_id = ? AND is_active = 1
                ORDER BY import_date DESC
                LIMIT 20
            """, (instance_id,))
            recent_cvs = [
                {"cv_name": row[0], "package_path": row[1], "import_date": row[2]}
                for row in cursor.fetchall()
            ]

        return {
            **instance,
            "cv_count": cv_count,
            "package_count": package_count,
            "top_packages": top_packages,
            "recent_cvs": recent_cvs
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get instance details: {str(e)}")


@router.delete("/package-mappings/instance/{instance_id}")
async def delete_instance(instance_id: int) -> dict:
    """Delete a HANA instance and all its package mappings."""

    try:
        db = PackageMappingDB()

        import sqlite3
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()

            # Check if instance exists
            cursor.execute("SELECT instance_name FROM hana_instances WHERE instance_id = ?", (instance_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Instance not found")

            instance_name = row[0]

            # Delete mappings
            cursor.execute("DELETE FROM package_mappings WHERE instance_id = ?", (instance_id,))
            mappings_deleted = cursor.rowcount

            # Delete import history
            cursor.execute("DELETE FROM import_history WHERE instance_id = ?", (instance_id,))

            # Delete instance
            cursor.execute("DELETE FROM hana_instances WHERE instance_id = ?", (instance_id,))

            conn.commit()

        return {
            "message": f"Instance '{instance_name}' deleted successfully",
            "instance_id": instance_id,
            "mappings_deleted": mappings_deleted
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete instance: {str(e)}")


@router.get("/package-mappings/search")
async def search_mappings(
    q: str = Query(..., description="Search query for CV name"),
    instance_name: str = Query(None, description="Filter by instance name")
) -> dict:
    """Search for package mappings by CV name."""

    try:
        db = PackageMappingDB()
        results = db.search_cv(q, instance_name)

        return {
            "query": q,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/package-mappings/statistics")
async def get_statistics() -> dict:
    """Get overall package mapping statistics."""

    try:
        db = PackageMappingDB()
        stats = db.get_statistics()

        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.get("/package-mappings/history")
async def get_import_history(limit: int = Query(10, description="Number of history entries to return")) -> dict:
    """Get import history."""

    try:
        db = PackageMappingDB()
        history = db.get_import_history(limit)

        return {
            "history": history,
            "count": len(history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


@router.get("/config/defaults")
async def get_default_config() -> dict:
    """Get default configuration template."""

    return {
        "client": "PROD",
        "language": "EN",
        "schema_overrides": {},
        "currency_udf_name": None,
        "currency_rates_table": None,
        "currency_schema": None,
    }

