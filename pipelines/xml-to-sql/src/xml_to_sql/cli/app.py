"""Typer-based command line interface for xml_to_sql."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import typer

from ..config import Config, ScenarioConfig, load_config
from ..domain.types import DatabaseMode, HanaVersion
from ..parser import parse_scenario
from ..parser.xml_format_detector import detect_xml_format, get_recommended_hana_version
from ..sql import render_scenario
from ..bw import generate_bw_wrapper
from ..bw.wrapper_generator import detect_is_bw_object
from lxml import etree

app = typer.Typer(help="Convert SAP HANA calculation view XML to intermediate IR and SQL.")


@app.command()
def convert(
    config: Path = typer.Option(..., "--config", "-c", help="Path to a YAML configuration file."),
    scenario: Optional[List[str]] = typer.Option(
        None,
        "--scenario",
        "-s",
        help="Limit execution to specific scenario ids or output names.",
    ),
    mode: Optional[str] = typer.Option(
        None,
        "--mode",
        "-m",
        help="Override database mode (snowflake/hana). Overrides config setting.",
    ),
    hana_version: Optional[str] = typer.Option(
        None,
        "--hana-version",
        help="HANA version for HANA mode (1.0, 2.0, 2.0_SPS01, 2.0_SPS03). Overrides config setting.",
    ),
    list_only: bool = typer.Option(
        False,
        "--list-only",
        "-l",
        help="Do not parse files; only show which scenarios would be processed.",
    ),
) -> None:
    """Parse configured scenarios and (eventually) emit SQL artefacts."""

    config_obj = load_config(config)
    selected = config_obj.select_scenarios(scenario)

    if not selected:
        message = "No scenarios matched the requested filters." if scenario else "No scenarios enabled in config."
        typer.secho(message, fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    for scenario_cfg in selected:
        source_path = scenario_cfg.resolve_source_path(config_obj.source_directory)
        target_path = config_obj.resolve_target_path(scenario_cfg)
        typer.echo(f"[plan] {source_path} -> {target_path}")
        if list_only:
            continue

        if not source_path.exists():
            typer.secho(f"  ERROR: Source file not found: {source_path}", fg=typer.colors.RED)
            continue

        try:
            scenario_ir = parse_scenario(source_path)
            _describe_scenario(scenario_ir, scenario_cfg, target_path)

            client = scenario_cfg.overrides.effective_client(config_obj.default_client)
            language = scenario_cfg.overrides.effective_language(config_obj.default_language)
            output_name = scenario_cfg.output_name or scenario_cfg.id
            view_schema = scenario_cfg.overrides.effective_schema(config_obj.default_view_schema)

            # Build qualified view name with optional HANA package path
            # If hana_package is provided (e.g., "Macabi_BI.EYAL.EYAL_CDS"),
            # generate: _SYS_BIC.Macabi_BI.EYAL.EYAL_CDS/CV_NAME (without quotes - renderer will add them)
            # Otherwise: _SYS_BIC.CV_NAME or just CV_NAME
            # NOTE: Do NOT add quotes here - the SQL renderer's _quote_identifier will handle quoting
            if scenario_cfg.hana_package and scenario_cfg.database_mode == DatabaseMode.HANA:
                # Use package path with / separator (HANA catalog convention)
                view_name_with_package = f"{scenario_cfg.hana_package}/{output_name}"
                qualified_view_name = (
                    f'{view_schema}.{view_name_with_package}' if view_schema else view_name_with_package
                )
            else:
                qualified_view_name = f"{view_schema}.{output_name}" if view_schema else output_name
            
            # Detect if this is a BW object
            instance_type = scenario_cfg.instance_type or "auto"
            if instance_type == "auto":
                is_bw = detect_is_bw_object(scenario_ir)
                instance_type = "bw" if is_bw else "ecc"
                typer.echo(f"  Detected instance type: {instance_type}")
            else:
                is_bw = (instance_type == "bw")
            
            # For BW objects, generate wrapper instead of full expansion
            if is_bw:
                bw_package = scenario_cfg.bw_package or "DEFAULT_PACKAGE"
                typer.echo(f"  Using BW wrapper approach (package: {bw_package})")
                sql_content = generate_bw_wrapper(
                    scenario_ir,
                    bw_package=bw_package,
                    view_name=output_name
                )
                
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(sql_content, encoding="utf-8")
                typer.secho(f"  ✓ BW wrapper generated: {target_path}", fg=typer.colors.GREEN)
                continue
            
            # Determine database mode (priority: CLI > scenario > global config)
            if mode:
                try:
                    mode_enum = DatabaseMode(mode.lower())
                except ValueError:
                    typer.secho(f"  WARNING: Invalid mode '{mode}', using scenario config", fg=typer.colors.YELLOW)
                    mode_enum = scenario_cfg.database_mode
            else:
                mode_enum = scenario_cfg.database_mode
            
            # Determine HANA version (priority: CLI > scenario > auto-detect > default)
            if hana_version:
                try:
                    hana_ver_enum = HanaVersion(hana_version)
                except ValueError:
                    typer.secho(f"  WARNING: Invalid HANA version '{hana_version}', using scenario config", fg=typer.colors.YELLOW)
                    hana_ver_enum = scenario_cfg.hana_version
            else:
                hana_ver_enum = scenario_cfg.hana_version
            
            # Detect XML format for context
            try:
                tree = etree.parse(source_path)
                root = tree.getroot()
                xml_format = detect_xml_format(root)
                # Auto-detect version if needed
                if mode_enum == DatabaseMode.HANA and not hana_ver_enum:
                    hana_ver_enum = get_recommended_hana_version(root, hana_ver_enum)
            except Exception:
                xml_format = None

                sql_content, warnings = render_scenario(
                scenario_ir,
                schema_overrides=config_obj.schema_overrides,
                client=client,
                language=language,
                database_mode=mode_enum,
                hana_version=hana_ver_enum,
                xml_format=xml_format,
                create_view=True,
                    view_name=qualified_view_name,
                currency_udf=config_obj.currency.udf_name,
                currency_schema=config_obj.currency.schema,
                currency_table=config_obj.currency.rates_table,
                return_warnings=True,  # Capture warnings
                validate=True,  # Re-enable validation
            )

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(sql_content, encoding="utf-8")
            typer.secho(f"  ✓ SQL generated: {target_path}", fg=typer.colors.GREEN)

            # Display warnings if any
            if warnings:
                for warning in warnings:
                    typer.secho(f"  ⚠ WARNING: {warning}", fg=typer.colors.YELLOW)

        except Exception as e:
            typer.secho(f"  ERROR: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)


@app.command("list")
def list_scenarios(
    config: Path = typer.Option(..., "--config", "-c", help="Path to a YAML configuration file."),
) -> None:
    """Display scenarios defined in the configuration file."""

    config_obj = load_config(config)
    if not config_obj.scenarios:
        typer.echo("No scenarios defined.")
        raise typer.Exit()

    for scenario_cfg in config_obj.scenarios:
        status = "enabled" if scenario_cfg.enabled else "disabled"
        source_path = scenario_cfg.resolve_source_path(config_obj.source_directory)
        typer.echo(f"{scenario_cfg.id} [{status}] -> {source_path}")


def _describe_scenario(scenario_ir, scenario_cfg: ScenarioConfig, target_path: Path) -> None:
    nodes_count = len(scenario_ir.nodes)
    filters_count = sum(len(node.filters) for node in scenario_ir.nodes.values())
    calculated_count = sum(len(node.calculated_attributes) for node in scenario_ir.nodes.values())
    logical_model_status = "present" if scenario_ir.logical_model else "absent"

    typer.echo(f"  Scenario ID: {scenario_ir.metadata.scenario_id}")
    typer.echo(f"  Nodes parsed: {nodes_count}")
    typer.echo(f"  Filters detected: {filters_count}")
    typer.echo(f"  Calculated columns: {calculated_count}")
    typer.echo(f"  Logical model: {logical_model_status}")
    typer.echo(f"  Planned SQL target: {target_path}")


__all__ = ["app", "convert", "list_scenarios"]

