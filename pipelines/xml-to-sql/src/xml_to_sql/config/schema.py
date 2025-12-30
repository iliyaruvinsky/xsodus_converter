"""Configuration models for the xml_to_sql pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ..domain.types import DatabaseMode, HanaVersion


@dataclass(slots=True)
class ScenarioOverrides:
    """Per-scenario override values."""

    client: Optional[str] = None
    language: Optional[str] = None
    schema: Optional[str] = None

    def effective_client(self, default_client: str) -> str:
        return self.client or default_client

    def effective_language(self, default_language: str) -> str:
        return self.language or default_language

    def effective_schema(self, default_schema: Optional[str]) -> Optional[str]:
        return self.schema or default_schema


@dataclass(slots=True)
class ScenarioConfig:
    """Configuration for a single calculation scenario."""

    id: str
    database_mode: DatabaseMode = DatabaseMode.SNOWFLAKE
    hana_version: Optional[HanaVersion] = HanaVersion.HANA_2_0
    hana_package: Optional[str] = None  # HANA package path: "Macabi_BI.EYAL.EYAL_CDS"
    instance_type: Optional[str] = None  # 'ecc', 'bw', 'auto'
    bw_package: Optional[str] = None  # For BW wrapper: "Macabi_BI.COOM"
    source: Optional[str] = None
    output_name: Optional[str] = None
    enabled: bool = True
    overrides: ScenarioOverrides = field(default_factory=ScenarioOverrides)

    def resolve_source_path(self, base_dir: Path) -> Path:
        """Return the path to the source XML for this scenario."""

        filename = self.source or f"{self.id}.XML"
        return (base_dir / filename).resolve()


@dataclass(slots=True)
class CurrencyConfig:
    """Names for currency conversion artefacts."""

    udf_name: Optional[str] = None
    rates_table: Optional[str] = None
    schema: Optional[str] = None


@dataclass(slots=True)
class Config:
    """Top-level configuration for the conversion pipeline."""

    source_directory: Path
    target_directory: Path
    default_client: str = "PROD"
    default_language: str = "EN"
    default_database_mode: DatabaseMode = DatabaseMode.SNOWFLAKE
    default_hana_version: HanaVersion = HanaVersion.HANA_2_0
    schema_overrides: Dict[str, str] = field(default_factory=dict)
    default_view_schema: Optional[str] = None
    currency: CurrencyConfig = field(default_factory=CurrencyConfig)
    scenarios: List[ScenarioConfig] = field(default_factory=list)

    def select_scenarios(self, requested: Optional[Iterable[str]] = None) -> List[ScenarioConfig]:
        """Return the list of scenarios that should be processed."""

        if requested is None:
            selected = [scenario for scenario in self.scenarios if scenario.enabled]
        else:
            requested_set = {value.strip() for value in requested if value}
            selected = [
                scenario
                for scenario in self.scenarios
                if scenario.enabled and (scenario.id in requested_set or scenario.output_name in requested_set)
            ]
        return selected

    def resolve_target_path(self, scenario: ScenarioConfig) -> Path:
        """Compute the expected SQL file path for a scenario."""

        output_name = scenario.output_name or scenario.id
        return (self.target_directory / f"{output_name}.sql").resolve()


__all__ = [
    "Config",
    "CurrencyConfig",
    "ScenarioConfig",
    "ScenarioOverrides",
]

