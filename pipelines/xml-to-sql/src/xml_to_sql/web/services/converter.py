"""Service for converting XML to SQL."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

from lxml import etree

logger = logging.getLogger(__name__)

from ...domain.types import DatabaseMode, HanaVersion
from ...parser.xml_format_detector import detect_xml_format, get_recommended_hana_version
from ...sql import render_scenario
from ...sql.corrector import AutoFixConfig, CorrectionResult, auto_correct_sql
from ...sql.validator import (
    ValidationResult,
    analyze_query_complexity,
    validate_expressions,
    validate_hana_sql,
    validate_performance,
    validate_query_completeness,
    validate_snowflake_specific,
    validate_sql,
    validate_sql_structure,
)
from ...abap import generate_abap_report


@dataclass
class ConversionStage:
    """Represents a single stage in the conversion process."""
    
    stage_name: str
    status: str  # 'pending', 'in_progress', 'completed', 'failed'
    timestamp: Optional[datetime] = None
    duration_ms: Optional[int] = None
    details: dict = field(default_factory=dict)
    xml_snippet: Optional[str] = None
    sql_snippet: Optional[str] = None
    error: Optional[str] = None


class ConversionResult:
    """Result of a conversion operation."""

    def __init__(
        self,
        sql_content: str,
        scenario_id: Optional[str] = None,
        warnings: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
        error: Optional[str] = None,
        validation: Optional[ValidationResult] = None,
        validation_logs: Optional[list[str]] = None,
        corrections: Optional[CorrectionResult] = None,
        stages: Optional[list[ConversionStage]] = None,
        abap_content: Optional[str] = None,
    ):
        self.sql_content = sql_content
        self.scenario_id = scenario_id
        self.warnings = warnings or []
        self.metadata = metadata or {}
        self.error = error
        self.validation = validation
        self.validation_logs = validation_logs or []
        self.corrections = corrections
        self.stages = stages or []
        self.abap_content = abap_content


def convert_xml_to_sql(
    xml_content: bytes,
    database_mode: str = "hana",
    hana_version: Optional[str] = None,
    hana_package: Optional[str] = None,
    target_schema: Optional[str] = "SAPABAP1",
    client: str = "PROD",
    language: str = "EN",
    schema_overrides: Optional[dict[str, str]] = None,
    view_schema: Optional[str] = "SAPABAP1",
    currency_udf_name: Optional[str] = None,
    currency_rates_table: Optional[str] = None,
    currency_schema: Optional[str] = None,
    auto_fix: bool = False,
    auto_fix_config: Optional[AutoFixConfig] = None,
    on_stage_update: Optional[callable] = None,
) -> ConversionResult:
    """
    Convert XML content to SQL with mode and version awareness.

    Args:
        xml_content: XML file content as bytes
        database_mode: Target database mode (snowflake/hana)
        hana_version: HANA version for version-specific SQL (when mode=hana)
        hana_package: HANA package path (e.g., Macabi_BI.EYAL.EYAL_CDS)
        target_schema: Target schema where tables reside (e.g., SAPABAP1)
        client: Default client value
        language: Default language value
        schema_overrides: Dictionary of schema name overrides
        view_schema: Schema where generated view should be created (HANA mode)
        currency_udf_name: Currency conversion UDF name
        currency_rates_table: Exchange rates table name
        currency_schema: Schema for currency artifacts
        auto_fix: Enable auto-correction of SQL issues
        auto_fix_config: Configuration for auto-correction
        on_stage_update: Optional callback function called after each stage completes.
                        Receives the completed ConversionStage object.

    Returns:
        ConversionResult with SQL content and metadata
    """
    # Initialize stage tracking
    stages: list[ConversionStage] = []
    
    def _start_stage(name: str) -> tuple[int, datetime]:
        """Start a new stage and return start time."""
        start_time = time.time()
        start_dt = datetime.now()
        stage = ConversionStage(
            stage_name=name,
            status='in_progress',
            timestamp=start_dt,
        )
        stages.append(stage)
        return int(start_time * 1000), start_dt
    
    def _complete_stage(start_ms: int, details: Optional[dict] = None,
                        xml_snippet: Optional[str] = None, sql_snippet: Optional[str] = None):
        """Mark current stage as completed."""
        if stages:
            stages[-1].status = 'completed'
            stages[-1].duration_ms = int(time.time() * 1000) - start_ms
            if details:
                stages[-1].details = details
            if xml_snippet:
                stages[-1].xml_snippet = xml_snippet
            if sql_snippet:
                stages[-1].sql_snippet = sql_snippet
            # Call callback if provided
            if on_stage_update:
                on_stage_update(stages[-1])
    
    def _fail_stage(start_ms: int, error: str):
        """Mark current stage as failed."""
        if stages:
            stages[-1].status = 'failed'
            stages[-1].duration_ms = int(time.time() * 1000) - start_ms
            stages[-1].error = error
    
    try:
        # Parse database mode and version
        try:
            mode_enum = DatabaseMode(database_mode.lower())
        except ValueError:
            mode_enum = DatabaseMode.SNOWFLAKE  # Default to Snowflake
        
        hana_version_enum: Optional[HanaVersion] = None
        if hana_version:
            try:
                hana_version_enum = HanaVersion(hana_version)
            except ValueError:
                hana_version_enum = HanaVersion.HANA_2_0  # Default
        
        # Stage 1: Parse and Validate XML
        start_ms, start_dt = _start_stage("Parse XML")
        
        # Parse XML from bytes
        tree = etree.parse(BytesIO(xml_content))
        root = tree.getroot()
        
        # Detect XML format
        try:
            xml_format = detect_xml_format(root)
        except ValueError:
            xml_format = None  # Unknown format
        
        # Auto-detect HANA version if in HANA mode and not explicitly provided
        if mode_enum == DatabaseMode.HANA and not hana_version_enum:
            hana_version_enum = get_recommended_hana_version(root, hana_version_enum)

        # Validate that this is a SAP HANA calculation view XML
        # Check for expected namespace and root element structure
        hana_calc_namespace = "http://www.sap.com/ndb/BiModelCalculation.ecore"
        hana_view_namespace = "http://www.sap.com/ndb/ViewModelView.ecore"
        root_qname = etree.QName(root)
        root_local = root_qname.localname
        root_tag = root_qname.text

        is_hana_xml = False

        if root_local == "scenario":
            if hana_calc_namespace in root.nsmap.values():
                is_hana_xml = True
            if root.get("id") is not None:
                is_hana_xml = True
        elif root_local == "ColumnView":
            if hana_view_namespace in root.nsmap.values() or root_qname.namespace == hana_view_namespace:
                # ColumnView has inline nodes without separate dataSources section
                has_view_nodes = len(root.findall("./{*}viewNode")) > 0
                if has_view_nodes:
                    is_hana_xml = True
        else:
            # Additional check: look for expected HANA calculation view elements
            has_data_sources = len(root.findall(".//{*}dataSources")) > 0 or len(root.findall(".//{*}DataSource")) > 0
            has_calc_views = len(root.findall(".//{*}calculationViews")) > 0 or len(root.findall(".//{*}calculationView")) > 0
            if has_data_sources or has_calc_views:
                is_hana_xml = True
        
        if not is_hana_xml:
            return ConversionResult(
                sql_content="",
                error=(
                    "This XML file does not appear to be a SAP HANA calculation view XML.\n\n"
                    "Expected: A SAP HANA calculation view XML file with:\n"
                    "  - Root element: <scenario> or <Calculation:scenario>\n"
                    "  - Namespace: http://www.sap.com/ndb/BiModelCalculation.ecore\n"
                    "  - Elements: <dataSources>, <calculationViews>, etc.\n\n"
                    "The uploaded file appears to be a different type of XML.\n"
                    "Please upload a valid SAP HANA calculation view XML file."
                ),
                validation_logs=[],
            )

        # Extract scenario ID from XML
        scenario_id = root.get("id") or root.get("name")
        
        # Get XML snippet for display
        xml_snippet = etree.tostring(root, encoding='unicode', pretty_print=True)[:500] + "..."
        
        _complete_stage(start_ms, details={
            "scenario_id": scenario_id,
            "root_element": root_tag,
            "namespace_count": len(root.nsmap),
        }, xml_snippet=xml_snippet)

        # Stage 2: Build Intermediate Representation
        start_ms, start_dt = _start_stage("Build IR")
        
        # Parse scenario to IR
        # parse_scenario expects a Path, so we create a temporary file
        import tempfile

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".xml", delete=False) as tmp:
            # Handle both string and bytes input
            if isinstance(xml_content, str):
                tmp.write(xml_content.encode('utf-8'))
            else:
                tmp.write(xml_content)
            tmp_path = Path(tmp.name)

        try:
            from ...parser.scenario_parser import parse_scenario
            scenario_ir = parse_scenario(tmp_path)
        except (etree.XMLSyntaxError, etree.ParseError) as parse_error:
            return ConversionResult(
                sql_content="",
                error=(
                    f"Failed to parse the XML file as a SAP HANA calculation view.\n\n"
                    f"Parse error: {str(parse_error)}\n\n"
                    f"This could mean:\n"
                    f"  - The XML file is malformed or corrupted\n"
                    f"  - The XML file is not a SAP HANA calculation view\n"
                    f"  - The XML structure doesn't match expected HANA calculation view format\n\n"
                    f"Please verify that you're uploading a valid SAP HANA calculation view XML file."
                ),
                validation_logs=[],
            )
        except (KeyError, AttributeError, ValueError) as struct_error:
            return ConversionResult(
                sql_content="",
                error=(
                    f"Failed to parse the XML structure as a SAP HANA calculation view.\n\n"
                    f"Error: {str(struct_error)}\n\n"
                    f"This XML file appears to be missing required HANA calculation view elements:\n"
                    f"  - <dataSources> section\n"
                    f"  - <calculationViews> section\n"
                    f"  - Or other required calculation view structure\n\n"
                    f"Please verify that you're uploading a valid SAP HANA calculation view XML file.\n"
                    f"If this is a HANA calculation view, it may be using an unsupported format or version."
                ),
                validation_logs=[],
            )
        finally:
            # Clean up temp file
            tmp_path.unlink()

        # Build metadata
        nodes_count = len(scenario_ir.nodes)
        filters_count = sum(len(node.filters) for node in scenario_ir.nodes.values())
        calculated_count = sum(len(node.calculated_attributes) for node in scenario_ir.nodes.values())
        logical_model_present = scenario_ir.logical_model is not None

        metadata = {
            "scenario_id": scenario_ir.metadata.scenario_id,
            "nodes_count": nodes_count,
            "filters_count": filters_count,
            "calculated_attributes_count": calculated_count,
            "logical_model_present": logical_model_present,
        }
        
        _complete_stage(start_ms, details={
            "nodes_count": nodes_count,
            "filters_count": filters_count,
            "calculated_attributes_count": calculated_count,
            "data_sources_count": len(scenario_ir.data_sources),
            "logical_model_present": logical_model_present,
        })

        # Determine view name / schema placement
        scenario_id = scenario_ir.metadata.scenario_id or "GENERATED_VIEW"
        effective_view_schema = (view_schema.strip() if view_schema else None)
        if mode_enum == DatabaseMode.HANA:
            # Default schema for HANA views is _SYS_BIC unless explicitly overridden
            if effective_view_schema is None:
                effective_view_schema = "_SYS_BIC"

        # Build qualified view name
        # CRITICAL HANA RULE: CREATE VIEW uses simple name only, package paths are for CV REFERENCES
        # - CREATE VIEW statement: "_SYS_BIC"."CV_NAME" AS ...
        # - CV references in JOINs: JOIN "_SYS_BIC"."Package.Path/CV_NAME" ON ...
        # Package mappings are applied later in SQL renderer for CV references, NOT here
        qualified_view_name = (
            f"{effective_view_schema}.{scenario_id}" if effective_view_schema else scenario_id
        )

        # Stage 3: Generate SQL
        start_ms, start_dt = _start_stage("Generate SQL")
        
        # Add mode/version info to stage details
        mode_info = {
            "database_mode": database_mode,
            "hana_version": hana_version if hana_version else "auto-detected",
            "xml_format": xml_format.value if xml_format else "unknown"
        }
        
        # Render to SQL with warnings (disable validation to capture results separately)
        sql_content, warnings = render_scenario(
            scenario_ir,
            schema_overrides=schema_overrides or {},
            target_schema=target_schema,
            client=client,
            language=language,
            database_mode=mode_enum,
            hana_version=hana_version_enum,
            xml_format=xml_format,
            create_view=True,
            view_name=qualified_view_name,
            currency_udf=currency_udf_name,
            currency_schema=currency_schema,
            currency_table=currency_rates_table,
            return_warnings=True,
            validate=False,  # Validate separately to capture results
        )
        
        # Get SQL snippet for display
        sql_snippet = sql_content[:500] + "..." if len(sql_content) > 500 else sql_content
        
        # Merge mode info with completion details
        completion_details = {
            **mode_info,
            "sql_length": len(sql_content),
            "warnings_count": len(warnings),
            "cte_count": sql_content.count(" AS ("),
        }
        
        _complete_stage(start_ms, details=completion_details, sql_snippet=sql_snippet)

        # Stage 4: Validate SQL
        start_ms, start_dt = _start_stage("Validate SQL")
        
        # Perform validation separately to capture results
        validation_result = ValidationResult()
        
        validation_logs: list[str] = []

        def _format_log(name: str, result: ValidationResult) -> str:
            status = "FAILED" if result.has_errors else "OK"
            return (
                f"{name}: {status} "
                f"(errors={len(result.errors)}, warnings={len(result.warnings)}, info={len(result.info)})"
            )

        # Phase 1: Structure validation
        structure_result = validate_sql_structure(sql_content)
        validation_result.merge(structure_result)
        validation_logs.append(_format_log("SQL Structure", structure_result))
        
        # Completeness validation (need render context)
        from ...sql.renderer import RenderContext, _topological_sort
        ctx = RenderContext(
            scenario_ir,
            schema_overrides or {},
            client,
            language,
            currency_udf_name,
            currency_schema,
            currency_rates_table,
        )
        # Populate CTE aliases for validation
        ordered_nodes = _topological_sort(scenario_ir)
        for node_id in ordered_nodes:
            if node_id in scenario_ir.data_sources:
                continue
            if node_id in scenario_ir.nodes:
                ctx.cte_aliases[node_id] = node_id.lower().replace("_", "_")
        
        completeness_result = validate_query_completeness(scenario_ir, sql_content, ctx)
        validation_result.merge(completeness_result)
        validation_logs.append(_format_log("Query Completeness", completeness_result))
        
        # Phase 2: Performance validation
        performance_result = validate_performance(sql_content, scenario_ir)
        validation_result.merge(performance_result)
        validation_logs.append(_format_log("Performance Checks", performance_result))
        
        # Phase 2: Snowflake-specific validation
        snowflake_result = validate_snowflake_specific(sql_content)
        validation_result.merge(snowflake_result)
        validation_logs.append(_format_log("Snowflake Specific Checks", snowflake_result))
        
        # Phase 2: Query complexity analysis
        complexity_result = analyze_query_complexity(sql_content, scenario_ir)
        validation_result.merge(complexity_result)
        validation_logs.append(_format_log("Query Complexity Analysis", complexity_result))

        # Phase 3: Advanced validation (optional - if schema metadata available)
        expression_result = validate_expressions(scenario_ir)
        validation_result.merge(expression_result)
        validation_logs.append(_format_log("Expression Validation", expression_result))
        
        _complete_stage(start_ms, details={
            "is_valid": validation_result.is_valid,
            "error_count": len(validation_result.errors),
            "warning_count": len(validation_result.warnings),
            "info_count": len(validation_result.info),
        })

        # Phase 4: Auto-correction (if enabled)
        correction_result: Optional[CorrectionResult] = None
        final_sql = sql_content
        
        # Auto-Correct SQL stage (only if auto_fix is enabled)
        if auto_fix:
            start_correct_ms, start_correct_dt = _start_stage("Auto-Correct SQL")
            if auto_fix_config is None:
                auto_fix_config = AutoFixConfig.default()
            
            correction_result = auto_correct_sql(
                sql_content,
                validation_result,
                scenario_ir,
                auto_fix_config,
            )
            
            if correction_result.corrections_applied:
                final_sql = correction_result.corrected_sql
                # Add correction notes to warnings
                for correction in correction_result.corrections_applied:
                    warnings.append(f"Auto-fixed: {correction.description}")
                
                _complete_stage(start_correct_ms, details={
                    "corrections_applied": len(correction_result.corrections_applied),
                    "issues_fixed": len(correction_result.issues_fixed),
                    "issues_remaining": len(correction_result.issues_remaining),
                }, sql_snippet=final_sql[:500] if len(final_sql) > 500 else final_sql)
            else:
                # No corrections were applied, but stage was attempted
                _complete_stage(start_correct_ms, details={
                    "corrections_applied": 0,
                    "message": "No issues found that could be auto-corrected",
                })
        else:
            # Auto-correction disabled - mark as skipped
            skip_stage = ConversionStage(
                stage_name="Auto-Correct SQL",
                status="pending",
                timestamp=datetime.now(),
            )
            skip_stage.details = {"skipped": True, "reason": "Auto-correction disabled"}
            stages.append(skip_stage)

        _complete_stage(start_ms, details={
            "is_valid": validation_result.is_valid,
            "total_issues": len(validation_result.errors) + len(validation_result.warnings),
            "auto_fix_applied": auto_fix and correction_result is not None and len(correction_result.corrections_applied) > 0,
        })

        # ABAP generation is now on-demand via separate API endpoint
        return ConversionResult(
            sql_content=final_sql,
            scenario_id=scenario_id,
            warnings=warnings,
            metadata=metadata,
            validation=validation_result,
            validation_logs=validation_logs,
            corrections=correction_result,
            stages=stages,
            abap_content=None,  # Generated on-demand
        )

    except etree.XMLSyntaxError as xml_error:
        return ConversionResult(
            sql_content="",
            error=(
                f"Invalid XML file format.\n\n"
                f"Expected: A SAP HANA calculation view XML file\n\n"
                f"XML parsing error: {str(xml_error)}\n\n"
                f"This file is not valid XML. Please check:\n"
                f"  - The file is not corrupted\n"
                f"  - The file is actually an XML file\n"
                f"  - The XML syntax is correct (matching tags, proper encoding, etc.)\n"
                f"  - The file is a SAP HANA calculation view XML (not another type of XML)"
            ),
            validation_logs=[],
        )
    except Exception as e:
        error_msg = str(e)
        # Provide more context for common errors
        if "scenario" in error_msg.lower() or "calculation" in error_msg.lower():
            return ConversionResult(
                sql_content="",
                error=(
                    f"Failed to process the XML file as a SAP HANA calculation view.\n\n"
                    f"Error: {error_msg}\n\n"
                    f"This could mean:\n"
                    f"  - The XML file is not a SAP HANA calculation view\n"
                    f"  - The XML structure doesn't match expected format\n"
                    f"  - Required elements are missing or malformed\n\n"
                    f"Please verify that you're uploading a valid SAP HANA calculation view XML file."
                ),
                validation_logs=[],
            )
        return ConversionResult(
            sql_content="",
            error=(
                f"Conversion failed: {error_msg}\n\n"
                f"If this is a SAP HANA calculation view XML file, please check:\n"
                f"  - The file is not corrupted\n"
                f"  - The file matches the expected HANA calculation view format\n"
                f"  - All required elements are present"
            ),
            validation_logs=[],
        )

