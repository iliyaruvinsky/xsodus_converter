"""Pattern-based formula rewrite catalog loader."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Dict, Optional

import yaml


@dataclass(frozen=True)
class PatternRule:
    """Represents a regex-based expression rewrite rule.

    Pattern rules are applied BEFORE function name rewrites in the translation
    pipeline. They handle expression-level transformations that can't be done
    with simple function name substitution.

    Example:
        NOW() - 365  →  ADD_DAYS(CURRENT_DATE, -365)

    This requires regex pattern matching, not just function renaming.
    """

    name: str
    match: str  # Regex pattern (Python syntax, case-insensitive)
    hana: str  # Replacement template for HANA mode (use $1, $2 for capture groups)
    snowflake: str  # Replacement template for Snowflake mode
    description: Optional[str] = None


@lru_cache(maxsize=1)
def get_pattern_catalog() -> Dict[str, PatternRule]:
    """Load and return the pattern rewrite catalog.

    Patterns are loaded from patterns.yaml and cached for performance.
    The catalog is returned as a dictionary keyed by pattern name.

    Returns:
        Dictionary mapping pattern names to PatternRule objects.

    Raises:
        RuntimeError: If patterns.yaml is missing or cannot be loaded.

    Example:
        >>> catalog = get_pattern_catalog()
        >>> rule = catalog['now_minus_days']
        >>> print(rule.match)
        NOW\\s*\\(\\s*\\)\\s*-\\s*(\\d+)
        >>> print(rule.hana)
        ADD_DAYS(CURRENT_DATE, -$1)
    """

    try:
        data_path = resources.files("xml_to_sql.catalog.data").joinpath("patterns.yaml")
    except (AttributeError, ModuleNotFoundError) as exc:  # pragma: no cover
        raise RuntimeError("Pattern catalog resources are missing") from exc

    try:
        raw_text = data_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError("patterns.yaml catalog is missing") from exc

    payload = yaml.safe_load(raw_text) or {}
    rules: Dict[str, PatternRule] = {}

    for item in payload.get("patterns", []):
        name = (item or {}).get("name")
        match = (item or {}).get("match")
        if not name or not match:
            continue  # Skip invalid entries

        rule = PatternRule(
            name=name,
            match=match,
            hana=item.get("hana", ""),
            snowflake=item.get("snowflake", ""),
            description=item.get("description"),
        )
        rules[rule.name] = rule

    return rules
