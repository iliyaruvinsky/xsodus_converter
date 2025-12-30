"""Naming convention templates for corporate standards."""

from __future__ import annotations

from typing import Optional


def format_table_name(identifier: str, name: str, prefix: str = "TB_F") -> str:
    """Format a table name according to corporate convention: TB_F_<IDENTIFIER>_<NAME>."""
    return f"{prefix}_{identifier}_{name}".upper()


def format_view_name(identifier: str, name: str, prefix: str = "V_C") -> str:
    """Format a view name according to corporate convention: V_C_<IDENTIFIER>_<NAME>."""
    return f"{prefix}_{identifier}_{name}".upper()


def format_measure_name(identifier: str, name: str) -> str:
    """Format a measure name."""
    return f"{identifier}_{name}".upper()


def sanitize_identifier(value: str) -> str:
    """Sanitize an identifier to be SQL-safe."""
    cleaned = value.replace(" ", "_").replace("-", "_").replace(".", "_")
    cleaned = "".join(c if c.isalnum() or c == "_" else "" for c in cleaned)
    if cleaned and not cleaned[0].isalpha():
        cleaned = f"ID_{cleaned}"
    return cleaned.upper()


def apply_naming_template(
    scenario_id: str,
    output_name: Optional[str] = None,
    template: str = "V_C",
    identifier: Optional[str] = None,
) -> str:
    """Apply naming template to generate final object name."""

    if output_name:
        return sanitize_identifier(output_name)

    base_name = sanitize_identifier(scenario_id)
    ident = sanitize_identifier(identifier) if identifier else "DEFAULT"

    if template.startswith("V_C"):
        return format_view_name(ident, base_name, "V_C")
    if template.startswith("TB_F"):
        return format_table_name(ident, base_name, "TB_F")

    return f"{template}_{base_name}".upper()


__all__ = [
    "format_table_name",
    "format_view_name",
    "format_measure_name",
    "sanitize_identifier",
    "apply_naming_template",
]

