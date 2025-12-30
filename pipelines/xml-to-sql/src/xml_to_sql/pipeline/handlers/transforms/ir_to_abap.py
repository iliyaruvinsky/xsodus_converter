"""Handler for IR to Pure ABAP transformation."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from ..base import TransformHandler, StageResult


class IrToAbapHandler(TransformHandler):
    """Handler that converts IR directly to Pure ABAP code.

    This handler uses the pure ABAP generator to convert
    the Intermediate Representation (Scenario) to native ABAP code.

    Unlike SQL-to-ABAP which wraps SQL in EXEC SQL blocks,
    this generates pure ABAP SELECT statements that work on
    ANY SAP system regardless of database backend.
    """

    def execute(
        self,
        input_data: Any,
        config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> StageResult:
        """Convert IR (Scenario) to Pure ABAP code.

        Args:
            input_data: Scenario object from XML parser
            config: Block configuration
            context: Execution context

        Returns:
            StageResult with generated Pure ABAP code
        """
        start_time = time.time()
        block_id = config.get("_block_id", "ir-to-abap")
        block_name = config.get("_block_name", "IR to Pure ABAP")

        try:
            # Import pure ABAP generator
            from ....abap import generate_pure_abap_report
            from ....domain.models import Scenario

            # Validate input is a Scenario
            if not isinstance(input_data, Scenario):
                return self._create_error_result(
                    block_id=block_id,
                    block_name=block_name,
                    errors=[
                        f"Input must be a Scenario object, got {type(input_data).__name__}. "
                        "This handler requires IR output from XML parser, not SQL."
                    ],
                    start_time=start_time,
                )

            scenario = input_data

            # Get optional output fields from config
            output_fields = config.get("output_fields")

            # Generate Pure ABAP report
            abap_code = generate_pure_abap_report(
                scenario=scenario,
                output_fields=output_fields,
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
                errors=[f"Pure ABAP generation error: {str(e)}"],
                start_time=start_time,
            )

    def get_input_types(self) -> List[str]:
        """Accepts IR (Intermediate Representation) input."""
        return ["ir"]

    def get_output_type(self) -> str:
        """Produces ABAP output."""
        return "abap"

    def get_config_schema(self) -> Dict[str, Any]:
        """Return configuration schema for this handler."""
        return {
            "type": "object",
            "properties": {
                "output_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of fields to include in output",
                },
                "include_comments": {
                    "type": "boolean",
                    "description": "Include descriptive comments in generated code",
                    "default": True,
                },
            },
        }

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate configuration."""
        errors = []

        output_fields = config.get("output_fields")
        if output_fields is not None and not isinstance(output_fields, list):
            errors.append("output_fields must be a list of strings")

        return errors
