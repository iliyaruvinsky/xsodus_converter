"""Utilities for loading xml_to_sql configuration files."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from ..domain.types import DatabaseMode, HanaVersion
from .schema import Config, CurrencyConfig, ScenarioConfig, ScenarioOverrides


_DEFAULT_SOURCE_DIR = Path("Source (XML Files)")
_DEFAULT_TARGET_DIR = Path("Target (SQL Scripts)")


def load_config(path: str | Path) -> Config:
    """Load configuration from a YAML file."""

    config_path = Path(path).expanduser().resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        raw_data = yaml.safe_load(handle) or {}

    if not isinstance(raw_data, dict):
        raise ValueError("Configuration root must be a mapping.")

    base_dir = config_path.parent
    defaults = raw_data.get("defaults", {})
    schema_overrides = raw_data.get("schema_overrides", {})
    currency_data = raw_data.get("currency", {})
    scenarios_data = raw_data.get("scenarios", [])
    paths_data = raw_data.get("paths", {})

    source_directory = _resolve_directory(paths_data.get("source"), base_dir, _DEFAULT_SOURCE_DIR)
    target_directory = _resolve_directory(paths_data.get("target"), base_dir, _DEFAULT_TARGET_DIR)

    # Parse database mode and HANA version from defaults
    default_mode = _parse_database_mode(defaults.get("database_mode"))
    default_hana_ver = _parse_hana_version(defaults.get("hana_version"))
    
    config = Config(
        source_directory=source_directory,
        target_directory=target_directory,
        default_client=str(defaults.get("client", "PROD")),
        default_language=str(defaults.get("language", "EN")),
        default_database_mode=default_mode,
        default_hana_version=default_hana_ver,
        schema_overrides=_coerce_str_dict(schema_overrides),
        currency=_parse_currency(currency_data),
        scenarios=_parse_scenarios(scenarios_data, default_mode, default_hana_ver),
        default_view_schema=str(defaults.get("view_schema", "_SYS_BIC")),
    )
    return config


def _resolve_directory(value: Optional[str], base_dir: Path, fallback: Path) -> Path:
    if value:
        candidate = Path(value)
    else:
        candidate = fallback
    if not candidate.is_absolute():
        candidate = (base_dir / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return candidate


def _coerce_str_dict(values: Any) -> Dict[str, str]:
    if not values:
        return {}
    if not isinstance(values, dict):
        raise ValueError("Expected a mapping for schema_overrides.")
    return {str(key): str(val) for key, val in values.items()}


def _parse_currency(data: Any) -> CurrencyConfig:
    if not isinstance(data, dict):
        return CurrencyConfig()
    return CurrencyConfig(
        udf_name=data.get("udf_name") or data.get("udf"),
        rates_table=data.get("rates_table"),
        schema=data.get("schema"),
    )


def _parse_scenarios(
    data: Any, 
    default_mode: DatabaseMode, 
    default_hana_ver: HanaVersion
) -> List[ScenarioConfig]:
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError("Expected a list for scenarios.")
    scenarios: List[ScenarioConfig] = []
    for entry in data:
        if not isinstance(entry, dict):
            raise ValueError("Each scenario entry must be a mapping.")
        scenario_id = entry.get("id")
        if not scenario_id:
            raise ValueError("Scenario entry missing 'id'.")
        overrides = _parse_overrides(entry.get("overrides"))
        
        # Parse scenario-specific mode and version, fall back to defaults
        scenario_mode = _parse_database_mode(entry.get("database_mode"), default_mode)
        scenario_hana_ver = _parse_hana_version(entry.get("hana_version"), default_hana_ver)
        
        scenario = ScenarioConfig(
            id=str(scenario_id),
            database_mode=scenario_mode,
            hana_version=scenario_hana_ver,
            instance_type=entry.get("instance_type"),
            bw_package=entry.get("bw_package"),
            source=entry.get("source"),
            output_name=entry.get("output"),
            enabled=entry.get("enabled", True),
            overrides=overrides,
        )
        scenarios.append(scenario)
    return scenarios


def _parse_overrides(data: Any) -> ScenarioOverrides:
    if not data:
        return ScenarioOverrides()
    if not isinstance(data, dict):
        raise ValueError("Expected a mapping for scenario overrides.")
    return ScenarioOverrides(
        client=data.get("client"),
        language=data.get("language"),
        schema=data.get("schema"),
    )


def _parse_database_mode(value: Any, default: DatabaseMode = DatabaseMode.SNOWFLAKE) -> DatabaseMode:
    """Parse database mode from config value."""
    if not value:
        return default
    
    value_str = str(value).lower()
    try:
        return DatabaseMode(value_str)
    except ValueError:
        # Invalid mode, use default
        return default


def _parse_hana_version(value: Any, default: HanaVersion = HanaVersion.HANA_2_0) -> HanaVersion:
    """Parse HANA version from config value."""
    if not value:
        return default
    
    value_str = str(value)
    try:
        return HanaVersion(value_str)
    except ValueError:
        # Invalid version, use default
        return default


__all__ = ["load_config"]

