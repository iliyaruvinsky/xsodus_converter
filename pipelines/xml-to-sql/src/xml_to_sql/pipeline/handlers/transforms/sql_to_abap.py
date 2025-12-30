"""Handler for SQL to ABAP transformation."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from ..base import TransformHandler, StageResult


class SqlToAbapHandler(TransformHandler):
    """Handler that converts SQL to ABAP Report.

    This handler uses the existing ABAP generator to convert
    SQL (CREATE VIEW statements) to an ABAP Report program that:
    1. Creates the view using native SQL
    2. Fetches data using cursor
    3. Exports to CSV file
    """

    def execute(
        self,
        input_data: Any,
        config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> StageResult:
        """Convert SQL to ABAP Report.

        Args:
            input_data: SQL string from previous stage
            config: Block configuration
            context: Execution context

        Returns:
            StageResult with generated ABAP code
        """
        start_time = time.time()
        block_id = config.get("_block_id", "sql-to-abap")
        block_name = config.get("_block_name", "SQL to ABAP")

        try:
            # Import ABAP generator
            from ....abap import generate_abap_report

            # Get SQL content
            if not isinstance(input_data, str):
                return self._create_error_result(
                    block_id=block_id,
                    block_name=block_name,
                    errors=["Input must be SQL string"],
                    start_time=start_time,
                )

            sql_content = input_data

            # Get scenario ID from config or context
            scenario_id = config.get("scenario_id")
            if not scenario_id and context:
                # Try to get from context metadata
                scenario_id = context.get("scenario_id", "GENERATED")
            if not scenario_id:
                scenario_id = "GENERATED"

            # Get database mode from context (set by target handler)
            # Defaults to HANA if not specified
            database_mode = "hana"
            target_schema = None
            schema_overrides = None

            if context:
                # Database mode can come from target config
                target_config = context.get("target_config", {})
                database_mode = target_config.get("database_mode", "hana")
                target_schema = target_config.get("target_schema")
                schema_overrides = target_config.get("schema_overrides")

                # Also check direct context settings
                if "database_mode" in context:
                    database_mode = context["database_mode"]
                if "target_schema" in context:
                    target_schema = context["target_schema"]
                if "schema_overrides" in context:
                    schema_overrides = context["schema_overrides"]

            # Generate ABAP report with database-specific settings
            abap_code = generate_abap_report(
                sql_content=sql_content,
                scenario_id=scenario_id,
                database_mode=database_mode,
                target_schema=target_schema,
                schema_overrides=schema_overrides,
            )

            return self._create_success_result(
                block_id=block_id,
                block_name=block_name,
                content=abap_code,
                start_time=start_time,
            )

        except Exception as e:
            return self._create_error_result(
                block_id=block_id,
                block_name=block_name,
                errors=[f"ABAP generation error: {str(e)}"],
                start_time=start_time,
            )

    def get_input_types(self) -> List[str]:
        """Accepts SQL input."""
        return ["sql"]

    def get_output_type(self) -> str:
        """Produces ABAP output."""
        return "abap"

    def get_config_schema(self) -> Dict[str, Any]:
        """Return configuration schema for this handler."""
        return {
            "type": "object",
            "properties": {
                "scenario_id": {
                    "type": "string",
                    "description": "Scenario identifier for program naming",
                },
                "output_path": {
                    "type": "string",
                    "description": "Default output path for CSV export",
                    "default": "C:\\temp\\export.csv",
                },
                "database_mode": {
                    "type": "string",
                    "enum": ["hana", "sqlserver"],
                    "description": "Target database for SQL syntax (usually set by target block)",
                    "default": "hana",
                },
                "target_schema": {
                    "type": "string",
                    "description": "Override schema name for target database",
                },
                "schema_overrides": {
                    "type": "object",
                    "description": "Mapping of source schema names to target schemas",
                    "additionalProperties": {"type": "string"},
                },
            },
        }

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate configuration."""
        return []
