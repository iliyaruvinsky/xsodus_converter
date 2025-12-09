"""Structured conversion catalog loader."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Dict, Optional

import yaml


@dataclass(frozen=True)
class FunctionRule:
    """Represents a legacy helper/function rewrite rule."""

    name: str
    handler: str
    template: Optional[str] = None
    target: Optional[str] = None
    description: Optional[str] = None


@lru_cache(maxsize=1)
def get_function_catalog() -> Dict[str, FunctionRule]:
    """Load and return the function rewrite catalog keyed by function name."""

    try:
        data_path = resources.files("xml_to_sql.catalog.data").joinpath("functions.yaml")
    except (AttributeError, ModuleNotFoundError) as exc:  # pragma: no cover - defensive
        raise RuntimeError("Conversion catalog resources are missing") from exc

    try:
        raw_text = data_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError("functions.yaml conversion catalog is missing") from exc

    payload = yaml.safe_load(raw_text) or {}
    rules: Dict[str, FunctionRule] = {}
    for item in payload.get("functions", []):
        name = (item or {}).get("name")
        handler = (item or {}).get("handler")
        if not name or not handler:
            continue
        rule = FunctionRule(
            name=name.upper(),
            handler=handler,
            template=item.get("template"),
            target=item.get("target"),
            description=item.get("description"),
        )
        rules[rule.name] = rule

    return rules

