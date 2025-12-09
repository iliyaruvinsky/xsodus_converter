"""Translates HANA functions to target database SQL equivalents."""

from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

from ..domain import Expression, ExpressionType
from ..domain.types import DatabaseMode, HanaVersion
from ..catalog import FunctionRule, get_function_catalog, PatternRule, get_pattern_catalog


def translate_hana_function(func_name: str, args: List[Expression], ctx) -> str:
    """Translate a HANA function call to target database SQL.
    
    This function determines the target database mode from context and delegates
    to mode-specific translation functions.
    """
    mode = getattr(ctx, "database_mode", DatabaseMode.SNOWFLAKE)
    hana_version = getattr(ctx, "hana_version", None)
    
    if mode == DatabaseMode.HANA:
        return _translate_for_hana(func_name, args, ctx, hana_version)
    else:  # Snowflake or default
        return _translate_for_snowflake(func_name, args, ctx)


def _translate_for_snowflake(func_name: str, args: List[Expression], ctx) -> str:
    """Translate a HANA function call to Snowflake SQL."""

    func_name_upper = func_name.upper()
    arg_strs = [ctx._render_expression(arg, ctx.table_alias) for arg in args] if hasattr(ctx, "_render_expression") else []

    if func_name_upper == "IF":
        if len(args) >= 3:
            condition = arg_strs[0] if arg_strs else "NULL"
            then_expr = arg_strs[1] if len(arg_strs) > 1 else "NULL"
            else_expr = arg_strs[2] if len(arg_strs) > 2 else "NULL"
            return f"IFF({condition}, {then_expr}, {else_expr})"

    if func_name_upper in {"CASE", "CASE_WHEN"}:
        if len(args) >= 2:
            parts: List[str] = ["CASE"]
            i = 0
            while i < len(args) - 1:
                parts.append(f"WHEN {arg_strs[i]} THEN {arg_strs[i + 1]}")
                i += 2
            if i < len(args):
                parts.append(f"ELSE {arg_strs[i]}")
            parts.append("END")
            return " ".join(parts)

    if func_name_upper == "SUBSTRING" or func_name_upper == "SUBSTR":
        if len(args) >= 2:
            return f"SUBSTRING({arg_strs[0]}, {arg_strs[1]}{f', {arg_strs[2]}' if len(args) > 2 else ''})"

    if func_name_upper in {"CONCAT", "CONCATENATE"}:
        if len(args) >= 2:
            return " || ".join(f"COALESCE({arg}, '')" for arg in arg_strs)

    if func_name_upper == "LENGTH":
        if args:
            return f"LENGTH({arg_strs[0]})"

    if func_name_upper in {"UPPER", "UCASE"}:
        if args:
            return f"UPPER({arg_strs[0]})"

    if func_name_upper in {"LOWER", "LCASE"}:
        if args:
            return f"LOWER({arg_strs[0]})"

    if func_name_upper == "TRIM":
        if args:
            return f"TRIM({arg_strs[0]})"

    if func_name_upper in {"ROUND", "CEIL", "FLOOR", "ABS"}:
        if args:
            return f"{func_name_upper}({arg_strs[0]}{f', {arg_strs[1]}' if len(args) > 1 else ''})"

    if func_name_upper in {"COALESCE", "NVL", "IFNULL"}:
        if args:
            return f"COALESCE({', '.join(arg_strs)})"

    if func_name_upper == "TO_DATE":
        if args:
            date_format = arg_strs[1] if len(args) > 1 else "'YYYYMMDD'"
            return f"TO_DATE({arg_strs[0]}, {date_format})"

    if func_name_upper == "TO_TIMESTAMP":
        if args:
            ts_format = f", {arg_strs[1]}" if len(args) > 1 else ""
            return f"TO_TIMESTAMP({arg_strs[0]}{ts_format})"

    return None


def _translate_for_hana(func_name: str, args: List[Expression], ctx, version: Optional[HanaVersion]) -> str:
    """Translate a HANA function call for HANA SQL (keep as-is or version-aware transform)."""

    func_name_upper = func_name.upper()
    arg_strs = [ctx._render_expression(arg, ctx.table_alias) for arg in args] if hasattr(ctx, "_render_expression") else []

    # IF: Keep as IF() in HANA (not IFF)
    if func_name_upper == "IF":
        if len(args) >= 3:
            condition = arg_strs[0] if arg_strs else "NULL"
            then_expr = arg_strs[1] if len(arg_strs) > 1 else "NULL"
            else_expr = arg_strs[2] if len(arg_strs) > 2 else "NULL"
            return f"IF({condition}, {then_expr}, {else_expr})"

    # Legacy helpers - version-dependent
    if func_name_upper == "LEFTSTR":
        if version and version >= HanaVersion.HANA_2_0:
            # Modern HANA: Can use SUBSTRING
            if len(args) >= 2:
                return f"SUBSTRING({arg_strs[0]}, 1, {arg_strs[1]})"
        # Legacy HANA 1.0: Keep LEFTSTR
        if args:
            return f"LEFTSTR({', '.join(arg_strs)})"

    if func_name_upper == "RIGHTSTR":
        if version and version >= HanaVersion.HANA_2_0:
            # Modern HANA: Can use RIGHT
            if len(args) >= 2:
                return f"RIGHT({arg_strs[0]}, {arg_strs[1]})"
        # Legacy HANA 1.0: Keep RIGHTSTR
        if args:
            return f"RIGHTSTR({', '.join(arg_strs)})"

    # Most other functions are compatible between HANA and Snowflake
    # CASE, SUBSTRING, CONCAT, LENGTH, UPPER, LOWER, TRIM, ROUND, etc.
    # Use the same logic as Snowflake
    
    if func_name_upper in {"CASE", "CASE_WHEN"}:
        if len(args) >= 2:
            parts: List[str] = ["CASE"]
            i = 0
            while i < len(args) - 1:
                parts.append(f"WHEN {arg_strs[i]} THEN {arg_strs[i + 1]}")
                i += 2
            if i < len(args):
                parts.append(f"ELSE {arg_strs[i]}")
            parts.append("END")
            return " ".join(parts)

    if func_name_upper == "SUBSTRING" or func_name_upper == "SUBSTR":
        if len(args) >= 2:
            return f"SUBSTRING({arg_strs[0]}, {arg_strs[1]}{f', {arg_strs[2]}' if len(args) > 2 else ''})"

    if func_name_upper in {"CONCAT", "CONCATENATE"}:
        if len(args) >= 2:
            # HANA uses + for string concatenation (handled in formula translation)
            # But CONCAT function works in both
            return f"CONCAT({', '.join(arg_strs)})"

    if func_name_upper == "LENGTH":
        if args:
            return f"LENGTH({arg_strs[0]})"

    if func_name_upper in {"UPPER", "UCASE"}:
        if args:
            return f"UPPER({arg_strs[0]})"

    if func_name_upper in {"LOWER", "LCASE"}:
        if args:
            return f"LOWER({arg_strs[0]})"

    if func_name_upper == "TRIM":
        if args:
            return f"TRIM({arg_strs[0]})"

    if func_name_upper in {"ROUND", "CEIL", "FLOOR", "ABS"}:
        if args:
            return f"{func_name_upper}({arg_strs[0]}{f', {arg_strs[1]}' if len(args) > 1 else ''})"

    if func_name_upper in {"COALESCE", "NVL", "IFNULL"}:
        if args:
            return f"COALESCE({', '.join(arg_strs)})"

    if func_name_upper == "TO_DATE":
        if args:
            date_format = arg_strs[1] if len(args) > 1 else "'YYYYMMDD'"
            return f"TO_DATE({arg_strs[0]}, {date_format})"

    if func_name_upper == "TO_TIMESTAMP":
        if args:
            ts_format = f", {arg_strs[1]}" if len(args) > 1 else ""
            return f"TO_TIMESTAMP({arg_strs[0]}{ts_format})"
    
    # ADD_MONTHS version check
    if func_name_upper == "ADD_MONTHS":
        if version and version < HanaVersion.HANA_1_0:
            ctx.warnings.append(f"ADD_MONTHS not available in HANA < 1.0")
        if len(args) >= 2:
            return f"ADD_MONTHS({arg_strs[0]}, {arg_strs[1]})"

    return None


def translate_raw_formula(formula: str, ctx) -> str:
    """Translate a raw HANA formula expression to target database SQL."""

    result = formula

    if not result:
        return "NULL"

    result = _substitute_placeholders(result, ctx)

    # Apply mode-specific transformations
    mode = getattr(ctx, "database_mode", DatabaseMode.SNOWFLAKE)

    if mode == DatabaseMode.HANA:
        # HANA mode: Convert to CASE WHEN, convert IN to OR conditions
        # IMPORTANT ORDER:
        # 1. Apply PATTERN rewrites FIRST (NOW() - N → ADD_DAYS())
        # 2. Then catalog rewrites (function name mappings: string → TO_VARCHAR)
        # 3. Then convert IN to OR for HANA compatibility
        # 4. Then convert IF to CASE WHEN (HANA requires CASE in SELECT clauses)
        result = _apply_pattern_rewrites(result, ctx, mode)
        result = _apply_catalog_rewrites(result, ctx)
        result = _normalize_isnull_calls(result)
        result = _uppercase_if_statements(result)
        # NOTE: NOW() is now handled by pattern rewrites (NOW - N) and catalog (NOW -> CURRENT_TIMESTAMP)

        # BUG-020 FIX: Convert function-style IN() to operator-style
        # XML: IN(col, val1, val2) → SQL: col IN (val1, val2)
        result = _convert_in_function_to_operator(result)

        # BUG-020 FIX: HANA 2.0+ supports IN() natively, no need to convert to OR
        # Only convert IN→OR for HANA 1.x
        hana_version = getattr(ctx, "hana_version", None)
        # Handle both Enum and string values
        version_str = hana_version.value if hasattr(hana_version, 'value') else hana_version

        if version_str and str(version_str).startswith("1."):
            result = _convert_in_to_or_for_hana(result)

        result = _convert_if_to_case_for_hana(result)
        result = _translate_string_concat_to_hana(result)
        result = _translate_column_references(result, ctx)
    else:  # Snowflake mode
        # Snowflake mode: IF -> IFF, + -> ||
        # Apply pattern rewrites before catalog rewrites
        result = _apply_pattern_rewrites(result, ctx, mode)
        result = _translate_if_statements(result, ctx)
        result = _apply_catalog_rewrites(result, ctx)
        result = _translate_string_concatenation(result)
        result = _translate_column_references(result, ctx)

    return result


def _remove_parameter_clauses_hana(formula: str) -> str:
    """Remove entire parameter filter clauses BEFORE substitution (PRE-REMOVAL strategy).

    Detects and removes complete parameter patterns like:
    - ('$$IP_XXX$$' = '' OR condition)
    - ('$$IP_XXX$$' = 'default' OR (DATE("COL") >= DATE('$$IP_XXX$$')))
    - (IN($$IP_XXX$$,0) OR IN("COL",$$IP_XXX$$))

    This prevents malformed SQL from nested DATE() calls and unbalanced parentheses.

    Strategy:
    1. Find parameter clause patterns with balanced parentheses
    2. Remove entire clause including outer parens
    3. Clean up orphaned AND/OR connectors
    """
    import re

    result = formula
    max_iterations = 20  # Prevent infinite loops

    # BUG-031: Handle IF() expressions with parameter checks
    # Must match BEFORE IF() is converted to CASE WHEN
    # Original: if('$$IP_TRTNUM$$' != '', lpad('$$IP_TRTNUM$$', 30, '0'), '')
    # After substitution: if('''' != '', lpad('''', 30, '0'), '')
    # Result: NULL

    # Use same parenthesis-counting logic as _convert_if_to_case_for_hana()
    # to properly handle nested function calls with commas
    for _ in range(max_iterations):
        # Find IF( with parameter check patterns
        # Pattern 1: if('$$IP_XXX$$' ...) or Pattern 2: if('''' ...) or if('' ...)
        if_match = re.search(r'\bif\s*\(\s*\'(?:\$\$IP_[A-Z_]+\$\$|\'{0,3})\'\s*(!?=)\s*\'\'', result, re.IGNORECASE)
        if not if_match:
            break

        if_start = if_match.start()
        args_start = if_match.end()

        # Extract the three arguments using parenthesis counting
        args = []
        current = []
        depth = 1  # Already inside the IF(
        in_quote = False
        i = args_start

        while i < len(result) and depth > 0:
            c = result[i]

            # Track quote state
            if c == '"' or c == "'":
                in_quote = not in_quote

            if not in_quote:
                if c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
                    if depth == 0:
                        # End of IF() function
                        val = ''.join(current).strip()
                        if val:
                            args.append(val)
                        break
                elif c == ',' and depth == 1:
                    # Argument separator at top level
                    val = ''.join(current).strip()
                    if val:
                        args.append(val)
                    current = []
                    i += 1
                    continue

            current.append(c)
            i += 1

        if len(args) != 2:
            # Not a valid IF with 3 args (condition already consumed), skip
            break

        # BUG-031: Evaluate the IF() condition to return correct branch
        # When parameter is empty (''), evaluate the condition:
        #   if('' = '', then_val, else_val) → condition TRUE → return then_val
        #   if('' != '', then_val, else_val) → condition FALSE → return else_val
        if_end = i  # Position of closing )
        operator = if_match.group(1)  # Extract '=' or '!=' from regex capture group

        if operator == '=':
            # Condition: '' = '' → TRUE → return then_value (args[0])
            replacement = args[0] if args else "NULL"
        else:  # operator == '!='
            # Condition: '' != '' → FALSE → return else_value (args[1])
            replacement = args[1] if len(args) > 1 else "NULL"

        # Convert empty string literals to NULL for HANA SQL compatibility
        # HANA doesn't accept bare '' in calculated columns
        if replacement.strip() in ("''", "''''", '""'):
            replacement = "NULL"

        result = result[:if_start] + replacement + result[if_end + 1:]

    for iteration in range(max_iterations):
        # Track if we made any changes
        changed = False

        # Pattern 1: ('$$IP_XXX$$' = 'value' OR ...)
        # Need to handle nested parens carefully, especially DATE() calls
        # Match: opening paren, parameter check, OR, expression, closing paren

        # Find all parameter references first
        param_pattern = r"\$\$IP_[A-Z_]+\$\$"
        param_match = re.search(param_pattern, result)

        if not param_match:
            break  # No more parameters to process

        # Find the containing clause
        # Look for pattern: ( ... $$IP_XXX$$ ... OR ... )
        # Need to find the opening and closing parens that contain this parameter

        param_pos = param_match.start()

        # Scan backwards to find opening paren
        opening_paren = -1
        depth = 0
        in_quote = False

        for i in range(param_pos - 1, -1, -1):
            c = result[i]

            if c in ('"', "'") and (i == 0 or result[i-1] != '\\'):
                in_quote = not in_quote

            if not in_quote:
                if c == ')':
                    depth += 1
                elif c == '(':
                    if depth == 0:
                        # Check if this paren starts a parameter clause
                        # Look for pattern like: ('$$IP or (IN($$IP
                        ahead = result[i:param_pos + 30].upper()
                        if 'IP_' in ahead and ('=' in ahead or 'IN(' in ahead or 'IN (' in ahead):
                            opening_paren = i
                            break
                    depth -= 1

        if opening_paren == -1:
            # Couldn't find opening paren, skip this parameter
            # Replace it with empty string to avoid infinite loop
            result = result[:param_match.start()] + "''" + result[param_match.end():]
            changed = True
            continue

        # Scan forward from opening paren to find matching closing paren
        # AND check for OR keyword (parameter clauses have OR)
        closing_paren = -1
        depth = 0
        in_quote = False
        has_or = False

        for i in range(opening_paren, len(result)):
            c = result[i]

            if c in ('"', "'") and (i == 0 or result[i-1] != '\\'):
                in_quote = not in_quote

            if not in_quote:
                if c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
                    if depth == 0:
                        closing_paren = i
                        break
                # Check for OR keyword at depth 1 (top level inside this clause)
                elif depth == 1 and i + 3 <= len(result):
                    chunk = result[i:i+3].upper()
                    if chunk == ' OR' or chunk == 'OR ':
                        has_or = True

        if closing_paren == -1 or not has_or:
            # Not a valid parameter clause pattern, skip
            result = result[:param_match.start()] + "''" + result[param_match.end():]
            changed = True
            continue

        # Found a complete parameter clause: result[opening_paren:closing_paren+1]
        # Remove it, including the surrounding parens
        before = result[:opening_paren]
        after = result[closing_paren + 1:]

        # Check if we need to clean up AND/OR connectors
        # Look backward for AND/OR before opening_paren
        before_stripped = before.rstrip()
        if before_stripped.upper().endswith(' AND'):
            before = before_stripped[:-4]
        elif before_stripped.upper().endswith(' OR'):
            before = before_stripped[:-3]
        elif before_stripped.endswith('AND'):
            before = before_stripped[:-3]
        elif before_stripped.endswith('OR'):
            before = before_stripped[:-2]

        # Look forward for AND/OR after closing_paren
        after_stripped = after.lstrip()
        if after_stripped.upper().startswith('AND '):
            after = after_stripped[4:]
        elif after_stripped.upper().startswith('OR '):
            after = after_stripped[3:]

        result = before + after
        changed = True

    # Final cleanup: remove double spaces, orphaned empty parens from parameters, malformed fragments
    result = re.sub(r'\s+', ' ', result)  # Collapse multiple spaces
    # Only remove empty parens that are orphaned (preceded/followed by operators or parens)
    # Don't remove () from function calls like now()
    result = re.sub(r'[\s(]\(\s*\)[\s)]', '', result)  # Remove orphaned empty parens
    result = re.sub(r'\s*AND\s+AND\s*', ' AND ', result, flags=re.IGNORECASE)  # Double AND
    result = re.sub(r'\s*OR\s+OR\s*', ' OR ', result, flags=re.IGNORECASE)  # Double OR

    # Remove malformed parameter fragments that slipped through:
    # Pattern: (('' = 0) OR ...) or (('''' = '' OR ...)) or DATE('') or DATE('''')
    # These are leftover from IN() parameter patterns and DATE() with empty strings
    max_fragment_iterations = 20
    for _ in range(max_fragment_iterations):
        # Pattern 1: (('' = number) OR expression) - using '' or ''''
        fragment_match = re.search(r"\(\s*\(\s*''{2,4}\s*=\s*\d+\s*\)\s+OR\s+[^)]+\)", result, re.IGNORECASE)
        if fragment_match:
            result = result[:fragment_match.start()] + result[fragment_match.end():]
            continue

        # Pattern 2: (('' = '') OR expression) or (('''' = '' OR expression))
        fragment_match = re.search(r"\(\s*\(\s*''{2,4}\s*=\s*''{2,4}\s*\)\s+OR\s+[^)]+\)", result, re.IGNORECASE)
        if fragment_match:
            result = result[:fragment_match.start()] + result[fragment_match.end():]
            continue

        # Pattern 3: ('''' = '' OR expression) - four quotes pattern
        fragment_match = re.search(r"\(\s*''{2,4}\s*=\s*''{2,4}\s+OR\s+[^)]+\)", result, re.IGNORECASE)
        if fragment_match:
            result = result[:fragment_match.start()] + result[fragment_match.end():]
            continue

        # Pattern 4: (expression OR ('' = 0))
        fragment_match = re.search(r"\([^(]+\s+OR\s+\(\s*''{2,4}\s*=\s*\d+\s*\)\s*\)", result, re.IGNORECASE)
        if fragment_match:
            result = result[:fragment_match.start()] + result[fragment_match.end():]
            continue

        # Pattern 5: DATE('') or DATE('''') - malformed DATE calls with empty strings
        fragment_match = re.search(r"DATE\s*\(\s*''{2,4}\s*\)", result, re.IGNORECASE)
        if fragment_match:
            # Replace DATE('') with NULL
            result = result[:fragment_match.start()] + "NULL" + result[fragment_match.end():]
            continue

        # Pattern 6: (DATE(...) >= DATE('')) or (DATE(...) <= DATE(''))
        fragment_match = re.search(r"\(\s*DATE\([^)]+\)\s*[<>=]+\s*DATE\s*\(\s*''{2,4}\s*\)\s*\)", result, re.IGNORECASE)
        if fragment_match:
            result = result[:fragment_match.start()] + result[fragment_match.end():]
            continue

        # No more fragments found
        break

    # Clean up orphaned AND/OR after fragment removal
    result = re.sub(r'\s+AND\s+\)', ' )', result, flags=re.IGNORECASE)  # AND before closing paren
    result = re.sub(r'\s+OR\s+\)', ' )', result, flags=re.IGNORECASE)  # OR before closing paren
    result = re.sub(r'\(\s+AND\s+', '(', result, flags=re.IGNORECASE)  # AND after opening paren
    result = re.sub(r'\(\s+OR\s+', '(', result, flags=re.IGNORECASE)  # OR after opening paren
    result = re.sub(r'WHERE\s+AND\s+', 'WHERE ', result, flags=re.IGNORECASE)  # AND after WHERE
    result = re.sub(r'WHERE\s+OR\s+', 'WHERE ', result, flags=re.IGNORECASE)  # OR after WHERE

    return result.strip()


def _substitute_placeholders(text: str, ctx) -> str:
    """Replace $$client$$ and $$language$$ placeholders.

    For HANA mode with input parameters, use PRE-REMOVAL strategy to remove
    entire parameter filter clauses BEFORE substitution to avoid malformed SQL.
    """
    mode = getattr(ctx, "database_mode", DatabaseMode.SNOWFLAKE)

    result = text.replace("$$client$$", getattr(ctx, "client", "PROD"))
    result = result.replace("$$language$$", getattr(ctx, "language", "EN"))

    # For HANA mode, handle $$IP_*$$ parameters
    # HANA SQL views don't support PLACEHOLDER syntax like calculation views
    # Use PRE-REMOVAL strategy: Remove entire parameter clauses BEFORE substitution
    if mode == DatabaseMode.HANA:
        result = _remove_parameter_clauses_hana(result)

    return result


def _translate_if_statements(formula: str, ctx) -> str:
    """Translate HANA if() function calls to Snowflake IFF()."""

    pattern = r'if\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^)]+)\s*\)'
    def replace_if(match):
        condition = match.group(1).strip()
        then_expr = match.group(2).strip()
        else_expr = match.group(3).strip()
        return f"IFF({condition}, {then_expr}, {else_expr})"

    return re.sub(pattern, replace_if, formula, flags=re.IGNORECASE)


def _translate_string_concatenation(formula: str) -> str:
    """Translate HANA string concatenation to Snowflake || operator."""

    result = formula
    # Handle 'string'+column and column+'string' patterns
    # Replace '+ with || (string literal + something)
    result = re.sub(r"'\s*\+\s*", "' || ", result)
    # Replace +' with || (something + string literal)
    result = re.sub(r"\s*\+\s*'", " || '", result)
    # Replace + between non-string parts (column+column)
    result = re.sub(r'"([^"]+)"\s*\+\s*"([^"]+)"', r'"\1" || "\2"', result)
    result = re.sub(r'"([^"]+)"\s*\+\s*([^"+\s]+)', r'"\1" || \2', result)
    # Handle non-quoted column references before quoted ones
    result = re.sub(r"([^\"'\s]+)\s*\+\s*\"([^\"]+)\"", r'\1 || "\2"', result)
    return result


def _translate_string_concat_to_hana(formula: str) -> str:
    """Convert || to + for HANA string concatenation.
    
    Exception: Don't convert inside REGEXP_LIKE() - those need || for pattern building.
    """
    
    result = formula
    
    # Find all REGEXP_LIKE(...) calls and protect them from || → + conversion
    regexp_calls = []
    pattern = re.compile(r'REGEXP_LIKE\s*\(', re.IGNORECASE)
    
    for match in pattern.finditer(result):
        start = match.end() - 1  # Position of opening (
        # Find matching closing paren
        depth = 1
        i = match.end()
        in_quote = False
        
        while i < len(result) and depth > 0:
            c = result[i]
            if c in ('"', "'") and (i == 0 or result[i-1] != '\\'):
                in_quote = not in_quote
            if not in_quote:
                if c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
            i += 1
        
        if depth == 0:
            # Store the REGEXP_LIKE call content
            regexp_calls.append((match.start(), i, result[match.start():i]))
    
    # Replace || with + EXCEPT inside REGEXP_LIKE calls
    if not regexp_calls:
        # No REGEXP_LIKE - simple replacement
        result = re.sub(r'\|\|', '+', result)
    else:
        # Replace in segments, skipping REGEXP_LIKE sections
        parts = []
        last_end = 0
        
        for start, end, regexp_content in regexp_calls:
            # Convert || to + in the part before REGEXP_LIKE
            before = result[last_end:start]
            parts.append(before.replace('||', '+'))
            # Keep REGEXP_LIKE content as-is (with ||)
            parts.append(regexp_content)
            last_end = end
        
        # Convert || to + in the part after last REGEXP_LIKE
        after = result[last_end:]
        parts.append(after.replace('||', '+'))
        
        result = ''.join(parts)
    
    return result


def _uppercase_if_statements(formula: str) -> str:
    """Uppercase IF function calls for HANA (requires uppercase IF)."""
    
    # Replace lowercase if( with uppercase IF(
    # Use word boundary to avoid replacing "if" in other contexts
    result = re.sub(r'\bif\s*\(', 'IF(', formula, flags=re.IGNORECASE)
    
    return result


def _convert_if_to_case_for_hana(formula: str) -> str:
    """Convert IF() function to CASE WHEN for HANA.
    
    HANA may not support IF() in SELECT clause calculated columns.
    Convert: IF(condition, then_value, else_value)
    To: CASE WHEN condition THEN then_value ELSE else_value END
    """
    
    result = formula
    max_iterations = 20
    
    for _ in range(max_iterations):
        # Find "IF(" pattern (case insensitive but should be uppercase by now)
        if_match = re.search(r'\bIF\s*\(', result, re.IGNORECASE)
        if not if_match:
            break
        
        if_start = if_match.start()
        args_start = if_match.end()
        
        # Extract the three arguments: condition, then_expr, else_expr
        # Need to handle nested parens and commas
        args = []
        current = []
        depth = 1  # Already inside the IF(
        in_quote = False
        i = args_start
        
        while i < len(result) and depth > 0:
            c = result[i]
            
            # Track quote state
            if c == '"' or c == "'":
                in_quote = not in_quote
            
            if not in_quote:
                if c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
                    if depth == 0:
                        # End of IF() function
                        val = ''.join(current).strip()
                        if val:
                            args.append(val)
                        break
                elif c == ',' and depth == 1:
                    # Argument separator at top level
                    val = ''.join(current).strip()
                    if val:
                        args.append(val)
                    current = []
                    i += 1
                    continue
            
            current.append(c)
            i += 1
        
        if len(args) != 3:
            # Not a valid IF with 3 args, skip
            break
        
        condition = args[0]
        then_value = args[1]
        else_value = args[2]
        
        # For HANA, convert empty string '' to NULL in ELSE clauses
        # to avoid "invalid number" errors
        if else_value == "''":
            else_value = "NULL"
        
        # Build CASE WHEN
        case_expr = f"CASE WHEN {condition} THEN {then_value} ELSE {else_value} END"
        
        # Replace in result
        if_end = i  # Position of closing )
        result = result[:if_start] + case_expr + result[if_end + 1:]
    
    return result


def _convert_in_function_to_operator(formula: str) -> str:
    """Convert function-style IN() to operator-style for HANA.

    XML uses: IN(column, 'a', 'b', 'c')
    HANA requires: column IN ('a', 'b', 'c')

    ====================================================================
    ⚠️ CRITICAL - BUG-020 FIX (SESSION 4, validated 66ms HANA execution)
    ====================================================================
    This function converts XML function-style IN() to HANA operator-style.

    WITHOUT this conversion:
    - SQL: IN(RIGHT("CALMONTH", 2), '01', '02', '03')
    - Error: "sql syntax error: incorrect syntax near IF"

    WITH this conversion:
    - SQL: RIGHT("CALMONTH", 2) IN ('01', '02', '03')
    - Result: ✅ HANA execution successful

    See: FIXES_AFTER_COMMIT_4eff5fb.md for full details
    ====================================================================
    """
    import re

    result = formula
    max_iterations = 20  # Prevent infinite loops
    iteration = 0
    search_start = 0  # Track where to start searching to avoid re-processing

    while iteration < max_iterations:
        iteration += 1

        # Find IN( pattern starting from search_start
        match = re.search(r'\bIN\s*\(', result[search_start:], re.IGNORECASE)
        if not match:
            break

        # Adjust positions relative to full string
        in_start = search_start + match.start()
        in_end = search_start + match.end()  # Position after "IN("

        # Find matching closing paren, tracking nested parens and quotes
        depth = 1
        i = in_end
        in_quote = False
        quote_char = None

        while i < len(result) and depth > 0:
            c = result[i]

            # Handle quotes
            if c in ('"', "'") and (i == 0 or result[i-1] != '\\'):
                if not in_quote:
                    in_quote = True
                    quote_char = c
                elif c == quote_char:
                    in_quote = False
                    quote_char = None

            if not in_quote:
                if c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1

            i += 1

        if depth != 0:
            # Couldn't find matching paren, break
            break

        close_paren = i - 1

        # Extract arguments: IN(arg1, arg2, arg3, ...)
        args_str = result[in_end:close_paren]

        # Split by comma at depth 0, respecting nested parens and quotes
        args = []
        current_arg = []
        paren_depth = 0  # Track parentheses depth INSIDE the arguments
        in_quote = False
        quote_char = None

        for j, c in enumerate(args_str):
            # Handle quotes
            if c in ('"', "'"):
                if not in_quote:
                    in_quote = True
                    quote_char = c
                elif c == quote_char and (j == 0 or args_str[j-1] != '\\'):
                    in_quote = False
                    quote_char = None

            if not in_quote:
                if c == '(':
                    paren_depth += 1
                elif c == ')':
                    paren_depth -= 1
                elif c == ',' and paren_depth == 0:
                    # This is a top-level comma - split here
                    args.append(''.join(current_arg).strip())
                    current_arg = []
                    continue

            current_arg.append(c)

        if current_arg:
            args.append(''.join(current_arg).strip())

        if len(args) < 2:
            # Not enough args, skip this IN
            break

        # First arg is the expression, rest are values
        expression = args[0]
        values = args[1:]

        # Build: expression IN (val1, val2, val3)
        values_list = ', '.join(values)
        replacement = f"{expression} IN ({values_list})"

        # Replace in result
        result = result[:in_start] + replacement + result[close_paren + 1:]

        # Move search_start past the replacement to avoid re-processing
        search_start = in_start + len(replacement)

    return result


def _convert_in_to_or_for_hana(formula: str) -> str:
    """Convert IN operator to OR conditions for HANA compatibility.
    
    HANA doesn't support IN operator inside IF() conditions in some contexts.
    Convert: (rightstr("CALMONTH", 2) IN ('a', 'b', 'c'))
    To: (rightstr("CALMONTH", 2) = 'a' OR rightstr("CALMONTH", 2) = 'b' OR rightstr("CALMONTH", 2) = 'c')
    """
    
    def convert_one_in_clause(text):
        """Convert one IN clause to OR conditions with proper quote/paren handling."""
        # Find " IN (" pattern
        in_pattern = re.compile(r'\s+IN\s*\(', re.IGNORECASE)
        match = in_pattern.search(text)
        
        if not match:
            return text, False
        
        in_start = match.start()
        in_end = match.end()  # Position right after "IN ("
        
        # Scan backwards from IN to find opening paren, tracking quotes and parens
        open_paren_pos = -1
        depth = 0
        in_quote = False
        
        for i in range(in_start - 1, -1, -1):
            c = text[i]
            
            # Track quote state (properly handle escaped quotes)
            if c in ('"', "'") and (i == 0 or text[i-1] != '\\'):
                in_quote = not in_quote
            
            if in_quote:
                continue
            
            # Track paren depth
            if c == ')':
                depth += 1
            elif c == '(':
                if depth == 0:
                    open_paren_pos = i
                    break
                depth -= 1
        
        if open_paren_pos == -1:
            return text, False
        
        # Extract expression (between opening paren and IN)
        expr = text[open_paren_pos + 1:in_start].strip()
        
        # Find closing paren for values list IN (...) - tracking quotes
        # We start at depth=1 because we're already past the opening paren of IN (
        depth = 1
        close_values_pos = in_end
        in_quote = False
        
        for i in range(in_end, len(text)):
            c = text[i]
            
            if c in ('"', "'") and (i == 0 or text[i-1] != '\\'):
                in_quote = not in_quote
            
            if in_quote:
                continue
            
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    close_values_pos = i
                    break
        
        # Extract values string (between IN ( and ))
        values_str = text[in_end:close_values_pos]
        
        # Split values by comma, respecting quotes
        values = []
        current = []
        in_quote = False
        
        for c in values_str:
            if c in ('"', "'"):
                in_quote = not in_quote
            
            if c == ',' and not in_quote:
                val = ''.join(current).strip()
                if val:
                    values.append(val)
                current = []
            else:
                current.append(c)
        
        if current:
            val = ''.join(current).strip()
            if val:
                values.append(val)
        
        # Build OR conditions
        or_parts = [f"{expr} = {val}" for val in values]
        or_clause = " OR ".join(or_parts)
        
        # Reconstruct with EXACTLY the same parentheses structure:
        # Original: (expr IN (vals))
        # New:      (expr = v1 OR expr = v2)
        # 
        # We have:
        # - open_paren_pos: position of ( before expr
        # - close_values_pos: position of ) after vals
        # - Need to find: closing ) for the whole clause
        
        # The closing paren for (expr IN (...)) should be right after close_values_pos
        # Let's scan forward skipping whitespace
        end_pos = close_values_pos + 1
        while end_pos < len(text) and text[end_pos] in (' ', '\t', '\n', '\r'):
            end_pos += 1
        
        # Check if we have a closing paren
        if end_pos < len(text) and text[end_pos] == ')':
            # We have outer paren: (expr IN (vals))
            # Replace with: (OR clause)
            before = text[:open_paren_pos]
            after = text[end_pos + 1:]
            new_text = before + f"({or_clause})" + after
        else:
            # No outer paren, just: expr IN (vals)
            # Replace with: (OR clause) - add parens
            before = text[:open_paren_pos]
            after = text[close_values_pos + 1:]
            new_text = before + f"({or_clause})" + after
        
        return new_text, True
    
    # Convert all IN clauses (max 10 iterations to prevent infinite loops)
    result = formula
    for iteration in range(10):
        result, changed = convert_one_in_clause(result)
        if not changed:
            break
    
    return result


def _translate_column_references(formula: str, ctx) -> str:
    """Translate quoted column references to proper SQL identifiers."""

    def replace_quoted(match):
        col_name = match.group(1)
        return f'"{col_name.upper()}"'

    result = re.sub(r'"([^"]+)"', replace_quoted, formula)
    return result


def _normalize_isnull_calls(formula: str) -> str:
    """Convert ISNULL(x) to (x IS NULL) for HANA SQL."""

    def replace(match: re.Match[str]) -> str:
        expr = match.group(1).strip()
        return f"(({expr}) IS NULL)"

    pattern = re.compile(r"\bisnull\s*\(\s*([^)]+?)\s*\)", re.IGNORECASE)
    return re.sub(pattern, replace, formula)


def _apply_pattern_rewrites(formula: str, ctx, mode: DatabaseMode) -> str:
    """Apply regex-based pattern rewrites BEFORE function name rewrites.

    This handles expression transformations that can't be done with simple
    function name substitution (e.g., NOW() - 365 → ADD_DAYS()).

    Pattern rewrites are applied in the order they appear in patterns.yaml.
    Each pattern is applied once in a single pass (no recursion).

    Args:
        formula: The formula string to transform
        ctx: Translation context (unused currently, but kept for consistency)
        mode: Target database mode (HANA or Snowflake)

    Returns:
        Formula with pattern rewrites applied

    Example:
        >>> _apply_pattern_rewrites("NOW() - 365", ctx, DatabaseMode.HANA)
        'ADD_DAYS(CURRENT_DATE, -365)'
    """

    catalog = get_pattern_catalog()
    result = formula

    for rule in catalog.values():
        # Get the mode-specific replacement template
        replacement_template = rule.hana if mode == DatabaseMode.HANA else rule.snowflake

        if not replacement_template:
            continue  # Skip if no replacement for this mode

        # Convert $1, $2, etc. to \1, \2, etc. for Python regex groups
        replacement = replacement_template.replace('$', '\\')

        # Apply regex substitution (case-insensitive)
        result = re.sub(
            rule.match,
            replacement,
            result,
            flags=re.IGNORECASE
        )

    return result


def _apply_catalog_rewrites(formula: str, ctx) -> str:
    """Apply structured catalog rewrites for legacy helper functions."""

    catalog = get_function_catalog()
    rewritten = formula
    for rule in catalog.values():
        rewritten = _rewrite_function_calls(rewritten, rule, ctx)
    return rewritten


def _rewrite_function_calls(formula: str, rule: FunctionRule, ctx) -> str:
    """Rewrite all occurrences of a function according to the provided rule."""

    pattern = re.compile(rf"\b{re.escape(rule.name)}\s*\(", re.IGNORECASE)
    pos = 0
    parts: List[str] = []

    while True:
        match = pattern.search(formula, pos)
        if not match:
            parts.append(formula[pos:])
            break

        call_start = match.start()
        open_paren_index = match.end() - 1
        close_index, args = _extract_function_arguments(formula, open_paren_index)

        if close_index == -1 or args is None:
            # Unbalanced parentheses; keep original text
            parts.append(formula[pos:match.end()])
            pos = match.end()
            continue

        replacement = _build_replacement(rule, args, ctx)
        if replacement is None:
            parts.append(formula[pos:close_index])
        else:
            parts.append(formula[pos:call_start])
            parts.append(replacement)

        pos = close_index

    return "".join(parts)


def _extract_function_arguments(text: str, open_paren_index: int) -> Tuple[int, Optional[List[str]]]:
    """Extract argument list starting at open parenthesis index.

    Returns tuple of (index after closing parenthesis, argument list). If parentheses
    are unbalanced the second element will be None and the index -1.
    """

    depth = 0
    i = open_paren_index
    args_start = open_paren_index + 1

    while i < len(text):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                args_segment = text[args_start:i]
                return i + 1, _split_arguments(args_segment)
        i += 1

    return -1, None


def _split_arguments(arg_string: str) -> List[str]:
    """Split a comma-separated argument string, respecting nesting and quotes."""

    args: List[str] = []
    current: List[str] = []
    depth = 0
    in_quote = False
    idx = 0
    length = len(arg_string)

    while idx < length:
        ch = arg_string[idx]

        if ch == "'":
            if in_quote and idx + 1 < length and arg_string[idx + 1] == "'":
                current.append("''")
                idx += 2
                continue
            in_quote = not in_quote
            current.append(ch)
            idx += 1
            continue

        if not in_quote:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth = max(depth - 1, 0)
            elif ch == "," and depth == 0:
                argument = "".join(current).strip()
                if argument:
                    args.append(argument)
                current = []
                idx += 1
                continue

        current.append(ch)
        idx += 1

    argument = "".join(current).strip()
    if argument:
        args.append(argument)

    return args


def _build_replacement(rule: FunctionRule, args: Sequence[str], ctx) -> Optional[str]:
    """Build the replacement expression for the rule using parsed arguments."""

    handler = rule.handler.lower()

    if handler == "template" and rule.template:
        try:
            return rule.template.format(*args)
        except IndexError:
            return None

    if handler == "rename" and rule.target:
        return f"{rule.target}({', '.join(args)})"

    if handler == "regexp_like":
        if not args:
            return None
        target = args[0]
        pattern = args[1] if len(args) > 1 else "'*'"
        translated_pattern = (
            f"'^' || REPLACE(REPLACE({pattern}, '*', '.*'), '?', '.') || '$'"
        )
        return f"REGEXP_LIKE({target}, {translated_pattern})"

    if handler == "in_list":
        if len(args) < 2:
            return None
        target, *options = args
        normalized_options = [_normalize_scalar(arg) for arg in options]
        return f"({target} IN ({', '.join(normalized_options)}))"

    return None


def _normalize_scalar(argument: str) -> str:
    """Normalize scalar arguments (e.g., convert double-quoted literals to single-quoted)."""

    stripped = argument.strip()
    if stripped.startswith('"') and stripped.endswith('"'):
        inner = stripped[1:-1].replace("'", "''")
        return f"'{inner}'"
    return stripped


__all__ = ["translate_hana_function", "translate_raw_formula"]

