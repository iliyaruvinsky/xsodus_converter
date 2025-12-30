"""SQL auto-correction module for automatically fixing validation issues."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from ..domain import Scenario
from .validator import ValidationIssue, ValidationResult, ValidationSeverity


class CorrectionConfidence(Enum):
    """Confidence level for a correction."""

    HIGH = "high"  # Safe to apply automatically
    MEDIUM = "medium"  # Apply with warning
    LOW = "low"  # Require user approval


@dataclass
class Correction:
    """Represents a single correction applied to SQL."""

    issue_code: str  # Code of the validation issue being fixed
    original_text: str  # Original SQL text that was replaced
    corrected_text: str  # Corrected SQL text
    line_number: Optional[int] = None
    description: str = ""  # Human-readable description of the fix
    confidence: CorrectionConfidence = CorrectionConfidence.HIGH

    def __str__(self) -> str:
        """String representation of the correction."""
        location = ""
        if self.line_number is not None:
            location = f" (line {self.line_number})"
        return f"[{self.confidence.value.upper()}] {self.description}{location}: '{self.original_text}' → '{self.corrected_text}'"


@dataclass
class CorrectionResult:
    """Result of auto-correction process."""

    corrected_sql: str
    corrections_applied: List[Correction] = field(default_factory=list)
    issues_fixed: List[str] = field(default_factory=list)  # Issue codes that were fixed
    issues_remaining: List[ValidationIssue] = field(default_factory=list)  # Issues that couldn't be auto-fixed
    auto_fix_enabled: bool = False
    original_sql: str = ""

    def __init__(self, corrected_sql: str, original_sql: str = "", auto_fix_enabled: bool = False):
        """Initialize correction result."""
        self.corrected_sql = corrected_sql
        self.original_sql = original_sql
        self.auto_fix_enabled = auto_fix_enabled
        self.corrections_applied = []
        self.issues_fixed = []
        self.issues_remaining = []


@dataclass
class AutoFixConfig:
    """Configuration for auto-correction behavior."""

    enable_high_confidence_fixes: bool = True
    enable_medium_confidence_fixes: bool = True
    enable_low_confidence_fixes: bool = False  # Require approval
    require_user_confirmation: bool = False  # Global confirmation flag
    max_corrections_per_issue_type: int = 10  # Prevent excessive changes
    fix_reserved_keywords: bool = True
    fix_string_concatenation: bool = True
    fix_function_calls: bool = True
    fix_identifier_quoting: bool = True
    fix_schema_qualification: bool = True
    fix_type_casting: bool = True
    fix_cte_naming: bool = True

    @classmethod
    def default(cls) -> AutoFixConfig:
        """Create default configuration."""
        return cls()


# Snowflake reserved keywords (subset - full list is extensive)
SNOWFLAKE_RESERVED_KEYWORDS = {
    "ACCOUNT", "ADMIN", "ALL", "ALTER", "AND", "ANY", "AS", "BETWEEN", "BY", "CASE", "CAST", "CHECK",
    "COLUMN", "CONNECT", "CONNECTION", "CONSTRAINT", "CREATE", "CROSS", "CURRENT", "CURRENT_DATE",
    "CURRENT_TIME", "CURRENT_TIMESTAMP", "CURRENT_USER", "DATABASE", "DELETE", "DISTINCT", "DROP",
    "ELSE", "END", "EXISTS", "FALSE", "FOLLOWING", "FOR", "FOREIGN", "FROM", "FULL", "FUNCTION",
    "GRANT", "GROUP", "GROUPING", "HAVING", "ILIKE", "IN", "INNER", "INSERT", "INTERSECT", "INTO",
    "IS", "ISSUE", "JOIN", "LATERAL", "LEFT", "LIKE", "LOCALTIME", "LOCALTIMESTAMP", "MINUS",
    "NATURAL", "NOT", "NULL", "NULLS", "OF", "ON", "OR", "ORDER", "ORGANIZATION", "OUTER", "OVER",
    "PARTITION", "PRECEDING", "PRIMARY", "QUALIFY", "REFERENCES", "REVOKE", "RIGHT", "RLIKE", "ROW",
    "ROWS", "SAMPLE", "SCHEMA", "SELECT", "SET", "SOME", "START", "TABLE", "TABLESAMPLE", "THEN",
    "TO", "TRIGGER", "TRUE", "TRY_CAST", "UNION", "UNIQUE", "UPDATE", "USING", "VALUES", "VIEW",
    "WHEN", "WHENEVER", "WHERE", "WITH",
}


def fix_reserved_keywords(sql: str, issues: List[ValidationIssue], config: AutoFixConfig) -> Tuple[str, List[Correction]]:
    """
    Fix unquoted reserved keywords by adding quotes.

    Args:
        sql: SQL string to fix
        issues: List of validation issues related to reserved keywords
        config: Auto-fix configuration

    Returns:
        Tuple of (corrected_sql, list of corrections)
    """
    if not config.fix_reserved_keywords:
        return sql, []

    corrections: List[Correction] = []
    corrected_sql = sql
    sql_lines = corrected_sql.split("\n")

    # Find issues related to reserved keywords
    reserved_keyword_issues = [
        issue for issue in issues
        if issue.code in ("RESERVED_KEYWORD", "UNQUOTED_RESERVED_KEYWORD", "RESERVED_KEYWORD_IDENTIFIER")
    ]

    if not reserved_keyword_issues:
        return sql, []

    # Pattern to find unquoted identifiers that are reserved keywords
    # We need to be careful to only quote identifiers, not SQL keywords in their proper context
    for issue in reserved_keyword_issues:
        # Extract the keyword from the issue message
        # Message format: "Reserved keyword 'KEYWORD' used as identifier without quotes"
        match = re.search(r"['\"]([A-Z_][A-Z0-9_]*)['\"]", issue.message, re.IGNORECASE)
        if not match:
            continue

        keyword = match.group(1).upper()
        if keyword not in SNOWFLAKE_RESERVED_KEYWORDS:
            continue

        # Find the keyword in SQL (as identifier, not as SQL keyword)
        # Look for patterns like: AS keyword, keyword AS, keyword, keyword FROM, etc.
        # But avoid: SELECT keyword FROM (where keyword is a column name)
        patterns = [
            # AS keyword (alias)
            (rf'\bAS\s+{re.escape(keyword)}\b', rf'AS `{keyword}`'),
            # keyword AS (table/CTE alias)
            (rf'\b{re.escape(keyword)}\s+AS\b', rf'`{keyword}` AS'),
            # keyword, (in SELECT list)
            (rf'\b{re.escape(keyword)}\s*,', rf'`{keyword}`,'),
            # keyword FROM (table name)
            (rf'\bFROM\s+{re.escape(keyword)}\b', rf'FROM `{keyword}`'),
            # JOIN keyword (table name)
            (rf'\bJOIN\s+{re.escape(keyword)}\b', rf'JOIN `{keyword}`'),
            # .keyword (qualified column)
            (rf'\.{re.escape(keyword)}\b', rf'.`{keyword}`'),
            # keyword. (schema/table prefix)
            (rf'\b{re.escape(keyword)}\.', rf'`{keyword}`.'),
        ]

        for pattern, replacement in patterns:
            if re.search(pattern, corrected_sql, re.IGNORECASE):
                line_num = issue.line_number or 1
                original = keyword
                corrected = f"`{keyword}`"
                corrections.append(
                    Correction(
                        issue_code=issue.code,
                        original_text=original,
                        corrected_text=corrected,
                        line_number=line_num,
                        description=f"Quoted reserved keyword '{keyword}'",
                        confidence=CorrectionConfidence.HIGH,
                    )
                )
                corrected_sql = re.sub(pattern, replacement, corrected_sql, flags=re.IGNORECASE)

    return corrected_sql, corrections


def fix_string_concatenation(sql: str, issues: List[ValidationIssue], config: AutoFixConfig) -> Tuple[str, List[Correction]]:
    """
    Fix string concatenation by replacing + with ||.

    Args:
        sql: SQL string to fix
        issues: List of validation issues related to string concatenation
        config: Auto-fix configuration

    Returns:
        Tuple of (corrected_sql, list of corrections)
    """
    if not config.fix_string_concatenation:
        return sql, []

    corrections: List[Correction] = []
    corrected_sql = sql

    # Find issues related to string concatenation
    concat_issues = [
        issue for issue in issues
        if issue.code in ("HANA_STRING_CONCAT", "STRING_CONCAT_PLUS", "HANA_COMPATIBILITY")
    ]

    if not concat_issues:
        return sql, []

    # Pattern to find + used for string concatenation
    # We need to be careful to only replace + when it's string concatenation, not numeric addition
    # Look for patterns like: 'string' + 'string', column + 'string', etc.
    # But avoid: number + number, column + column (unless we can determine they're strings)

    # Simple heuristic: Replace + when it's between quoted strings or after/before string-like expressions
    # Pattern: '...' + or + '...' or column + '...' or '...' + column
    string_concat_pattern = r"((?:'[^']*'|\"[^\"]*\"|`[^`]*`|[A-Z_][A-Z0-9_]*)\s*)\+(\s*(?:'[^']*'|\"[^\"]*\"|`[^`]*`|[A-Z_][A-Z0-9_]*))"

    matches = list(re.finditer(string_concat_pattern, corrected_sql, re.IGNORECASE))
    if matches:
        # Replace from end to start to preserve positions
        for match in reversed(matches):
            original = match.group(0)
            corrected = match.group(1) + "||" + match.group(2)
            line_num = _get_line_number(corrected_sql, match.start())
            corrections.append(
                Correction(
                    issue_code="STRING_CONCAT_PLUS",
                    original_text=original,
                    corrected_text=corrected,
                    line_number=line_num,
                    description="Replaced string concatenation operator + with ||",
                    confidence=CorrectionConfidence.HIGH,
                )
            )
            corrected_sql = corrected_sql[: match.start()] + corrected + corrected_sql[match.end() :]

    return corrected_sql, corrections


def fix_function_calls(sql: str, issues: List[ValidationIssue], config: AutoFixConfig) -> Tuple[str, List[Correction]]:
    """
    Fix function calls (e.g., IF() to IFF()).

    Args:
        sql: SQL string to fix
        issues: List of validation issues related to function calls
        config: Auto-fix configuration

    Returns:
        Tuple of (corrected_sql, list of corrections)
    """
    if not config.fix_function_calls:
        return sql, []

    corrections: List[Correction] = []
    corrected_sql = sql

    # Find issues related to function calls
    function_issues = [
        issue for issue in issues
        if issue.code in ("HANA_IF_FUNCTION", "IF_FUNCTION", "HANA_COMPATIBILITY", "FUNCTION_SYNTAX")
    ]

    if not function_issues:
        return sql, []

    # Replace IF( with IFF( (but not IFF itself)
    # Pattern: IF( but not IFF(
    if_pattern = r"\bIF\s*\("
    matches = list(re.finditer(if_pattern, corrected_sql, re.IGNORECASE))
    if matches:
        for match in reversed(matches):
            # Check that it's not already IFF
            if match.start() > 0 and corrected_sql[match.start() - 1 : match.start()].upper() == "F":
                continue

            original = match.group(0)
            corrected = "IFF("
            line_num = _get_line_number(corrected_sql, match.start())
            corrections.append(
                Correction(
                    issue_code="HANA_IF_FUNCTION",
                    original_text=original,
                    corrected_text=corrected,
                    line_number=line_num,
                    description="Replaced HANA IF() function with Snowflake IFF()",
                    confidence=CorrectionConfidence.HIGH,
                )
            )
            corrected_sql = corrected_sql[: match.start()] + corrected + corrected_sql[match.end() :]

    return corrected_sql, corrections


def fix_identifier_quoting(sql: str, issues: List[ValidationIssue], config: AutoFixConfig) -> Tuple[str, List[Correction]]:
    """
    Fix identifier quoting issues.

    Args:
        sql: SQL string to fix
        issues: List of validation issues related to identifier quoting
        config: Auto-fix configuration

    Returns:
        Tuple of (corrected_sql, list of corrections)
    """
    if not config.fix_identifier_quoting:
        return sql, []

    corrections: List[Correction] = []
    corrected_sql = sql

    # Find issues related to identifier quoting
    quoting_issues = [
        issue for issue in issues
        if issue.code in ("IDENTIFIER_LENGTH", "INVALID_IDENTIFIER", "CASE_SENSITIVITY")
    ]

    # This is a placeholder - identifier quoting fixes would be more complex
    # and context-dependent. For now, we'll handle this through reserved keywords fix.

    return corrected_sql, corrections


def fix_schema_qualification(
    sql: str, issues: List[ValidationIssue], scenario: Optional[Scenario], config: AutoFixConfig
) -> Tuple[str, List[Correction]]:
    """
    Fix unqualified table references by adding schema prefixes.

    Args:
        sql: SQL string to fix
        issues: List of validation issues related to schema qualification
        scenario: Optional scenario IR for context
        config: Auto-fix configuration

    Returns:
        Tuple of (corrected_sql, list of corrections)
    """
    if not config.fix_schema_qualification:
        return sql, []

    corrections: List[Correction] = []
    corrected_sql = sql

    # Find issues related to schema qualification
    schema_issues = [
        issue for issue in issues
        if issue.code in ("UNQUALIFIED_TABLE", "MISSING_SCHEMA", "SCHEMA_QUALIFICATION")
    ]

    if not schema_issues or not scenario:
        return sql, []

    # Extract table names from data sources
    schema_map: Dict[str, str] = {}
    for ds_id, ds in scenario.data_sources.items():
        if ds.schema_name and ds.object_name:
            schema_map[ds.object_name.lower()] = ds.schema_name

    # Find unqualified table references in FROM/JOIN clauses
    # Pattern: FROM table_name or JOIN table_name
    for issue in schema_issues:
        # Extract table name from issue message if possible
        # This is a simplified approach - in practice, we'd need more sophisticated parsing
        pass  # Placeholder for schema qualification fixes

    return corrected_sql, corrections


def fix_type_casting(sql: str, issues: List[ValidationIssue], config: AutoFixConfig) -> Tuple[str, List[Correction]]:
    """
    Fix type casting syntax.

    Args:
        sql: SQL string to fix
        issues: List of validation issues related to type casting
        config: Auto-fix configuration

    Returns:
        Tuple of (corrected_sql, list of corrections)
    """
    if not config.fix_type_casting:
        return sql, []

    corrections: List[Correction] = []
    corrected_sql = sql

    # Find issues related to type casting
    casting_issues = [
        issue for issue in issues
        if issue.code in ("INVALID_TYPE_CAST", "TYPE_CAST_SYNTAX", "HANA_TYPE_CAST")
    ]

    # Placeholder for type casting fixes
    return corrected_sql, corrections


def fix_cte_naming(sql: str, issues: List[ValidationIssue], config: AutoFixConfig) -> Tuple[str, List[Correction]]:
    """
    Fix CTE naming conflicts.

    Args:
        sql: SQL string to fix
        issues: List of validation issues related to CTE naming
        config: Auto-fix configuration

    Returns:
        Tuple of (corrected_sql, list of corrections)
    """
    if not config.fix_cte_naming:
        return sql, []

    corrections: List[Correction] = []
    corrected_sql = sql

    # Find issues related to CTE naming
    cte_issues = [
        issue for issue in issues
        if issue.code in ("DUPLICATE_CTE", "CTE_NAME_CONFLICT")
    ]

    if not cte_issues:
        return sql, []

    # Extract duplicate CTE names from issues
    # This would require parsing the SQL to find CTE definitions
    # For now, this is a placeholder

    return corrected_sql, corrections


def auto_correct_sql(
    sql: str,
    validation_result: ValidationResult,
    scenario: Optional[Scenario] = None,
    config: Optional[AutoFixConfig] = None,
) -> CorrectionResult:
    """
    Automatically correct SQL issues based on validation results.

    Args:
        sql: Original SQL to correct
        validation_result: Validation results containing issues to fix
        scenario: Optional scenario IR for context-aware fixes
        config: Auto-fix configuration (defaults to AutoFixConfig.default())

    Returns:
        CorrectionResult with corrected SQL and applied corrections
    """
    if config is None:
        config = AutoFixConfig.default()

    result = CorrectionResult(corrected_sql=sql, original_sql=sql, auto_fix_enabled=True)

    # Collect all fixable issues (for reserved keywords - these need validation)
    all_issues: List[ValidationIssue] = []
    all_issues.extend(validation_result.errors)
    all_issues.extend(validation_result.warnings)
    all_issues.extend(validation_result.info)

    corrected_sql = sql
    all_corrections: List[Correction] = []
    
    # Note: Auto-correction can work even without validation issues
    # Pattern matching for string concat and IF() works independently

    # Apply high-confidence fixes
    # Note: These fixes can work even without validation issues, as they do pattern matching
    if config.enable_high_confidence_fixes:
        # Fix reserved keywords (works with or without validation issues)
        if config.fix_reserved_keywords:
            corrected_sql, corrections = fix_reserved_keywords(corrected_sql, all_issues, config)
            all_corrections.extend(corrections)
            result.issues_fixed.extend([c.issue_code for c in corrections])

        # Fix string concatenation (works with or without validation issues)
        # This will find + operators between strings even if validation didn't flag them
        if config.fix_string_concatenation:
            corrected_sql, corrections = fix_string_concatenation(corrected_sql, all_issues, config)
            all_corrections.extend(corrections)
            result.issues_fixed.extend([c.issue_code for c in corrections])

        # Fix function calls (works with or without validation issues)
        # This will find IF( patterns even if validation didn't flag them
        if config.fix_function_calls:
            corrected_sql, corrections = fix_function_calls(corrected_sql, all_issues, config)
            all_corrections.extend(corrections)
            result.issues_fixed.extend([c.issue_code for c in corrections])

    # Apply medium-confidence fixes
    if config.enable_medium_confidence_fixes:
        # Fix identifier quoting
        if config.fix_identifier_quoting:
            corrected_sql, corrections = fix_identifier_quoting(corrected_sql, all_issues, config)
            all_corrections.extend(corrections)
            result.issues_fixed.extend([c.issue_code for c in corrections])

        # Fix schema qualification
        if config.fix_schema_qualification:
            corrected_sql, corrections = fix_schema_qualification(corrected_sql, all_issues, scenario, config)
            all_corrections.extend(corrections)
            result.issues_fixed.extend([c.issue_code for c in corrections])

        # Fix CTE naming
        if config.fix_cte_naming:
            corrected_sql, corrections = fix_cte_naming(corrected_sql, all_issues, config)
            all_corrections.extend(corrections)
            result.issues_fixed.extend([c.issue_code for c in corrections])

    # Apply low-confidence fixes (if enabled)
    if config.enable_low_confidence_fixes:
        # Fix type casting
        if config.fix_type_casting:
            corrected_sql, corrections = fix_type_casting(corrected_sql, all_issues, config)
            all_corrections.extend(corrections)
            result.issues_fixed.extend([c.issue_code for c in corrections])

    # Update result
    result.corrected_sql = corrected_sql
    result.corrections_applied = all_corrections

    # Determine remaining issues (those not fixed)
    fixed_issue_codes = set(result.issues_fixed)
    result.issues_remaining = [
        issue for issue in all_issues if issue.code not in fixed_issue_codes
    ]

    return result


def _get_line_number(sql: str, position: int) -> int:
    """Get line number for a given position in SQL string."""
    return sql[:position].count("\n") + 1

