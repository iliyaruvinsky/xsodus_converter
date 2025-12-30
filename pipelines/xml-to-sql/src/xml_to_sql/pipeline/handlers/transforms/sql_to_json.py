"""Handler for SQL to JSON transformation."""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple


class SqlToJsonHandler:
    """Handler that exports SQL structure as JSON.

    This handler parses SQL (CREATE VIEW statements) and generates
    a JSON representation of the view structure, including:
    - View metadata (name, schema)
    - Column definitions with types
    - Source tables/CTEs
    - Useful for documentation, analysis, or integration
    """

    def execute(
        self,
        input_data: Any,
        config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> "StageResult":
        """Convert SQL to JSON structure.

        Args:
            input_data: SQL string from previous stage
            config: Block configuration
            context: Execution context

        Returns:
            StageResult with JSON structure
        """
        from ..base import StageResult

        start_time = time.time()
        block_id = config.get("_block_id", "sql-to-json")
        block_name = config.get("_block_name", "SQL to JSON")

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

            # Parse SQL and build JSON structure
            json_structure = self._parse_sql_to_json(
                sql_content=sql_content,
                config=config,
                context=context,
            )

            # Format output
            indent = config.get("indent", 2)
            if indent:
                json_output = json.dumps(json_structure, indent=indent, ensure_ascii=False)
            else:
                json_output = json.dumps(json_structure, ensure_ascii=False)

            return self._create_success_result(
                block_id=block_id,
                block_name=block_name,
                content=json_output,
                start_time=start_time,
            )

        except Exception as e:
            return self._create_error_result(
                block_id=block_id,
                block_name=block_name,
                errors=[f"JSON export error: {str(e)}"],
                start_time=start_time,
            )

    def _parse_sql_to_json(
        self,
        sql_content: str,
        config: Dict[str, Any],
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Parse SQL and build JSON structure."""
        structure = {
            "type": "sql_view",
            "metadata": {},
            "view": {},
            "columns": [],
            "sources": [],
            "ctes": [],
            "raw_sql": sql_content if config.get("include_raw_sql", True) else None,
        }

        # Add context metadata if available
        if context:
            structure["metadata"]["scenario_id"] = context.get("scenario_id")
            structure["metadata"]["source_file"] = context.get("source_file")

        # Extract view name and schema
        schema, view_name = self._extract_view_name(sql_content)
        structure["view"]["name"] = view_name
        structure["view"]["schema"] = schema

        # Extract CTEs
        ctes = self._extract_ctes(sql_content)
        structure["ctes"] = ctes

        # Extract columns from final SELECT
        columns = self._extract_columns(sql_content)
        structure["columns"] = columns

        # Extract source tables
        sources = self._extract_sources(sql_content)
        structure["sources"] = sources

        # Add statistics
        structure["statistics"] = {
            "column_count": len(columns),
            "cte_count": len(ctes),
            "source_count": len(sources),
            "sql_length": len(sql_content),
        }

        # Remove null values for cleaner output
        if not config.get("include_raw_sql", True):
            del structure["raw_sql"]

        return structure

    def _extract_view_name(self, sql_content: str) -> Tuple[Optional[str], str]:
        """Extract schema and view name from CREATE VIEW statement."""
        # Pattern: CREATE VIEW "schema"."view_name"
        pattern = r'CREATE\s+VIEW\s+"([^"]+)"\s*\.\s*"([^"]+)"'
        match = re.search(pattern, sql_content, re.IGNORECASE)
        if match:
            return match.group(1), match.group(2)

        # Try without schema
        pattern2 = r'CREATE\s+VIEW\s+"([^"]+)"'
        match2 = re.search(pattern2, sql_content, re.IGNORECASE)
        if match2:
            return None, match2.group(1)

        return None, "UNKNOWN_VIEW"

    def _extract_ctes(self, sql_content: str) -> List[Dict[str, Any]]:
        """Extract CTE (Common Table Expression) definitions."""
        ctes = []

        # Pattern: name AS ( ... )
        # This is simplified - real parsing would need proper SQL parser
        cte_pattern = r'(\w+)\s+AS\s*\('
        matches = re.finditer(cte_pattern, sql_content, re.IGNORECASE)

        for match in matches:
            cte_name = match.group(1)
            # Skip common SQL keywords that might match
            if cte_name.upper() in ('SELECT', 'WHERE', 'FROM', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END'):
                continue
            ctes.append({
                "name": cte_name,
                "position": match.start(),
            })

        return ctes

    def _extract_columns(self, sql_content: str) -> List[Dict[str, Any]]:
        """Extract columns from the final SELECT statement."""
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

        for i, part in enumerate(column_parts):
            part = part.strip()
            if not part:
                continue

            col_info = {
                "index": i,
                "expression": part,
                "alias": None,
                "is_calculated": False,
            }

            # Check for AS alias
            as_match = re.search(r'^(.+?)\s+AS\s+"?([^"\s]+)"?\s*$', part, re.IGNORECASE)
            if as_match:
                expr = as_match.group(1).strip()
                alias = as_match.group(2).strip()
                col_info["expression"] = expr
                col_info["alias"] = alias
                col_info["is_calculated"] = self._is_calculated(expr)
            else:
                # No alias - extract column name
                identifiers = re.findall(r'"?[\w]+"?', part)
                if identifiers:
                    col_name = identifiers[-1].strip('"')
                    col_info["alias"] = col_name

            columns.append(col_info)

        return columns

    def _is_calculated(self, expression: str) -> bool:
        """Check if expression is a calculated field."""
        # Contains function call or operators
        return bool(re.search(r'[()+\-*/]|CASE|WHEN|COALESCE|CONCAT|SUBSTR', expression, re.IGNORECASE))

    def _extract_sources(self, sql_content: str) -> List[Dict[str, Any]]:
        """Extract source tables from SQL."""
        sources = []
        seen = set()

        # Pattern for FROM and JOIN clauses
        # FROM "schema"."table" or FROM table
        from_pattern = r'(?:FROM|JOIN)\s+"?([^"\s.]+)"?\s*\.\s*"?([^"\s,()]+)"?'
        matches = re.finditer(from_pattern, sql_content, re.IGNORECASE)

        for match in matches:
            schema = match.group(1)
            table = match.group(2)
            key = f"{schema}.{table}"

            if key not in seen:
                seen.add(key)
                sources.append({
                    "schema": schema,
                    "table": table,
                    "full_name": key,
                })

        # Also try without schema
        from_pattern2 = r'(?:FROM|JOIN)\s+"?([^"\s,.(]+)"?(?:\s|,|\))'
        matches2 = re.finditer(from_pattern2, sql_content, re.IGNORECASE)

        for match in matches2:
            table = match.group(1)
            # Skip SQL keywords
            if table.upper() in ('SELECT', 'WHERE', 'AND', 'OR', 'ON', 'AS', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'FULL', 'CROSS'):
                continue
            if table not in seen and f"%.{table}" not in ''.join(seen):
                seen.add(table)
                sources.append({
                    "schema": None,
                    "table": table,
                    "full_name": table,
                })

        return sources

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

    def get_input_types(self) -> List[str]:
        """Accepts SQL input."""
        return ["sql"]

    def get_output_type(self) -> str:
        """Produces JSON output."""
        return "json"

    def get_config_schema(self) -> Dict[str, Any]:
        """Return configuration schema for this handler."""
        return {
            "type": "object",
            "properties": {
                "indent": {
                    "type": "integer",
                    "description": "JSON indentation (0 for compact)",
                    "default": 2,
                },
                "include_raw_sql": {
                    "type": "boolean",
                    "description": "Include raw SQL in output",
                    "default": True,
                },
            },
        }

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate configuration."""
        errors = []
        indent = config.get("indent")
        if indent is not None and (not isinstance(indent, int) or indent < 0):
            errors.append("indent must be a non-negative integer")
        return errors

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
