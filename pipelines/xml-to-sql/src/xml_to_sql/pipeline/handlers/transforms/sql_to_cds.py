"""Handler for SQL to CDS transformation."""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple


class SqlToCdsHandler:
    """Handler that converts SQL to ABAP CDS View definition.

    This handler parses SQL (CREATE VIEW statements) and generates
    an equivalent ABAP CDS view definition that can be used in
    ABAP Development Tools (ADT).
    """

    def execute(
        self,
        input_data: Any,
        config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> "StageResult":
        """Convert SQL to CDS View definition.

        Args:
            input_data: SQL string from previous stage
            config: Block configuration
            context: Execution context

        Returns:
            StageResult with generated CDS definition
        """
        from ..base import StageResult

        start_time = time.time()
        block_id = config.get("_block_id", "sql-to-cds")
        block_name = config.get("_block_name", "SQL to CDS")

        try:
            # Get SQL content
            if not isinstance(input_data, str):
                return self._create_error_result(
                    block_id=block_id,
                    block_name=block_name,
                    errors=["Input must be SQL string"],
                    start_time=start_time,
                )

            sql_content = input_data

            # Get view name from config or extract from SQL
            view_name = config.get("view_name")
            if not view_name:
                view_name = self._extract_view_name(sql_content)

            # Generate CDS definition
            cds_code = self._generate_cds(
                sql_content=sql_content,
                view_name=view_name,
                config=config,
            )

            return self._create_success_result(
                block_id=block_id,
                block_name=block_name,
                content=cds_code,
                start_time=start_time,
            )

        except Exception as e:
            return self._create_error_result(
                block_id=block_id,
                block_name=block_name,
                errors=[f"CDS generation error: {str(e)}"],
                start_time=start_time,
            )

    def _extract_view_name(self, sql_content: str) -> str:
        """Extract view name from SQL CREATE VIEW statement."""
        # Pattern: CREATE VIEW "schema"."view_name" or CREATE VIEW "view_name"
        pattern = r'CREATE\s+VIEW\s+"?([^"\s.]+)"?\s*\.\s*"?([^"\s]+)"?'
        match = re.search(pattern, sql_content, re.IGNORECASE)
        if match:
            return match.group(2)

        # Try without schema
        pattern2 = r'CREATE\s+VIEW\s+"?([^"\s]+)"?'
        match2 = re.search(pattern2, sql_content, re.IGNORECASE)
        if match2:
            return match2.group(1)

        return "Z_CDS_VIEW"

    def _extract_columns(self, sql_content: str) -> List[Tuple[str, str, str]]:
        """Extract columns from the final SELECT statement.

        Returns:
            List of tuples: (expression, alias, source_field)
        """
        columns = []

        # Normalize whitespace
        sql_normalized = re.sub(r'\s+', ' ', sql_content)

        # Find the final SELECT...FROM
        select_pattern = r'SELECT\s+(.*?)\s+FROM\s+'
        matches = list(re.finditer(select_pattern, sql_normalized, re.IGNORECASE | re.DOTALL))

        if not matches:
            return columns

        # Take the last SELECT
        columns_str = matches[-1].group(1)

        # Split by comma, respecting parentheses
        column_parts = self._split_columns(columns_str)

        for part in column_parts:
            part = part.strip()
            if not part:
                continue

            # Check for AS alias
            as_match = re.search(r'^(.+?)\s+AS\s+"?([^"\s]+)"?\s*$', part, re.IGNORECASE)
            if as_match:
                expr = as_match.group(1).strip()
                alias = as_match.group(2).strip()
                # Try to extract source field from expression
                source = self._extract_source_field(expr)
                columns.append((expr, alias, source))
            else:
                # No alias - use the column name itself
                identifiers = re.findall(r'"?[\w]+"?', part)
                if identifiers:
                    col_name = identifiers[-1].strip('"')
                    columns.append((part.strip(), col_name, col_name))

        return columns

    def _extract_source_field(self, expr: str) -> str:
        """Extract source field name from expression."""
        # Simple case: table.column
        match = re.search(r'[\w]+\.["]*(\w+)["]*', expr)
        if match:
            return match.group(1)
        # Just an identifier
        match = re.search(r'["]*(\w+)["]*', expr)
        if match:
            return match.group(1)
        return "field"

    def _split_columns(self, columns_str: str) -> List[str]:
        """Split column list by commas, respecting parentheses."""
        parts = []
        current = ""
        depth = 0

        for char in columns_str:
            if char == '(':
                depth += 1
                current += char
            elif char == ')':
                depth -= 1
                current += char
            elif char == ',' and depth == 0:
                parts.append(current.strip())
                current = ""
            else:
                current += char

        if current.strip():
            parts.append(current.strip())

        return parts

    def _sanitize_cds_name(self, name: str) -> str:
        """Convert name to valid CDS identifier."""
        # Remove quotes and special characters
        clean = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        # Ensure doesn't start with number
        if clean and clean[0].isdigit():
            clean = '_' + clean
        return clean

    def _generate_cds(
        self,
        sql_content: str,
        view_name: str,
        config: Dict[str, Any],
    ) -> str:
        """Generate CDS view definition from SQL."""
        # Extract columns from SQL
        columns = self._extract_columns(sql_content)

        # Get CDS-specific config
        cds_name = config.get("cds_name") or f"Z_CDS_{self._sanitize_cds_name(view_name).upper()}"
        description = config.get("description") or f"CDS view generated from {view_name}"
        dev_class = config.get("dev_class") or "$TMP"

        # Extract base table from SQL (simplified - uses first FROM table)
        from_match = re.search(r'FROM\s+"?([^"\s.]+)"?\s*\.\s*"?([^"\s,]+)"?', sql_content, re.IGNORECASE)
        if from_match:
            base_schema = from_match.group(1)
            base_table = from_match.group(2)
        else:
            from_match2 = re.search(r'FROM\s+"?([^"\s,]+)"?', sql_content, re.IGNORECASE)
            base_schema = ""
            base_table = from_match2.group(1) if from_match2 else "BASE_TABLE"

        # Build CDS definition
        cds_lines = []

        # Header annotation
        cds_lines.append(f'@AbapCatalog.sqlViewName: \'{view_name[:16].upper()}\'')
        cds_lines.append(f'@AbapCatalog.compiler.compareFilter: true')
        cds_lines.append(f'@AbapCatalog.preserveKey: true')
        cds_lines.append(f'@AccessControl.authorizationCheck: #NOT_REQUIRED')
        cds_lines.append(f'@EndUserText.label: \'{description[:60]}\'')
        cds_lines.append('')
        cds_lines.append(f'define view {cds_name}')
        cds_lines.append(f'  as select from {base_table}')
        cds_lines.append('{')

        # Add columns
        for i, (expr, alias, source) in enumerate(columns):
            cds_alias = self._sanitize_cds_name(alias)
            is_last = (i == len(columns) - 1)
            comma = '' if is_last else ','

            # Simplified: just use key/alias mapping
            # In real CDS, we'd need proper field mapping
            if source.lower() == alias.lower():
                cds_lines.append(f'  {source}{comma}')
            else:
                cds_lines.append(f'  {source} as {cds_alias}{comma}')

        cds_lines.append('}')

        # Add comment with original SQL reference
        cds_lines.append('')
        cds_lines.append('// Generated from SQL:')
        # Add first few lines of original SQL as comment
        sql_preview = sql_content[:500].replace('\n', '\n// ')
        cds_lines.append(f'// {sql_preview}')
        if len(sql_content) > 500:
            cds_lines.append('// ... (truncated)')

        return '\n'.join(cds_lines)

    def get_input_types(self) -> List[str]:
        """Accepts SQL input."""
        return ["sql"]

    def get_output_type(self) -> str:
        """Produces CDS output."""
        return "cds"

    def get_config_schema(self) -> Dict[str, Any]:
        """Return configuration schema for this handler."""
        return {
            "type": "object",
            "properties": {
                "view_name": {
                    "type": "string",
                    "description": "Name for the generated CDS view",
                },
                "cds_name": {
                    "type": "string",
                    "description": "CDS entity name (defaults to Z_CDS_<view_name>)",
                },
                "description": {
                    "type": "string",
                    "description": "Description for the CDS view",
                },
                "dev_class": {
                    "type": "string",
                    "description": "Development class/package",
                    "default": "$TMP",
                },
            },
        }

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate configuration."""
        return []

    def _create_success_result(
        self,
        block_id: str,
        block_name: str,
        content: Any,
        start_time: float,
        warnings: Optional[List[str]] = None,
    ) -> "StageResult":
        """Helper to create a successful result."""
        from ..base import StageResult

        return StageResult(
            block_id=block_id,
            block_name=block_name,
            output_type=self.get_output_type(),
            content=content,
            success=True,
            errors=[],
            warnings=warnings or [],
            execution_time_ms=int((time.time() - start_time) * 1000),
        )

    def _create_error_result(
        self,
        block_id: str,
        block_name: str,
        errors: List[str],
        start_time: float,
    ) -> "StageResult":
        """Helper to create an error result."""
        from ..base import StageResult

        return StageResult(
            block_id=block_id,
            block_name=block_name,
            output_type=self.get_output_type(),
            content="",
            success=False,
            errors=errors,
            warnings=[],
            execution_time_ms=int((time.time() - start_time) * 1000),
        )
