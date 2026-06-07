"""Smlm external plugin macros helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from phage_annotator.smlm.external_plugin_types import (
    ExternalFijiPlugin,
    ManifestParameter,
    PluginExecutionManifest,
)


VALID_PARAM_TYPES = {"int", "float", "bool", "choice", "string"}
VALID_IMPL_TYPES = {"legacy_plugin", "plugin_filter", "extended_filter", "scijava_command"}
VALID_UI_DIALOG = {"none", "native", "scripted"}
VALID_THREADING = {"ui_thread", "worker_thread"}



def build_manifest_macro(plugin: ExternalFijiPlugin, arg_string: str) -> str:
    """Generate macro text from plugin manifest run command + template."""
    manifest = plugin.manifest
    if manifest is None:
        raise ValueError("Plugin has no strict execution manifest.")
    if manifest.macro_template:
        return (
            manifest.macro_template
            .replace("${PHAGE_PLUGIN_COMMAND}", manifest.run_command)
            .replace("${PHAGE_PLUGIN_ARG_STRING}", arg_string)
        )
    lines = [
        "setBatchMode(true);",
        f'run("{manifest.run_command}", "{_escape_macro(arg_string)}");',
    ]
    if bool(manifest.outputs.get("writes_results_table", False)):
        lines.append('if ("${PHAGE_SMLM_OUTPUT}" != "") saveAs("Results", "${PHAGE_SMLM_OUTPUT}");')
    if bool(manifest.outputs.get("updates_image", False)):
        lines.append("run(\"Update\");")
    return "\n".join(lines) + "\n"

def _resolve_plugin_dir(start_dir: Optional[Path]) -> Optional[Path]:
    """Resolve plugin dir for the current workflow."""
    roots: List[Path] = []
    if start_dir is not None:
        roots.append(Path(start_dir))
    roots.append(Path.cwd())
    roots.append(Path(__file__).resolve().parents[3])
    for root in roots:
        candidate = root / "external_plugins"
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None

def _slug(text: str) -> str:
    """Handle the slug helper flow."""
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return clean

def parse_plugins_config_from_jar(jar_path: str) -> tuple[List[str], List[str]]:
    """Parse legacy ImageJ `plugins.config` from jar, if present."""
    menu_entries: List[str] = []
    command_names: List[str] = []
    path = Path(jar_path)
    if not path.exists():
        return menu_entries, command_names
    try:
        with zipfile.ZipFile(path, "r") as zf:
            name = None
            for candidate in ("plugins.config", "Plugins.config", "config/plugins.config"):
                if candidate in zf.namelist():
                    name = candidate
                    break
            if name is None:
                return menu_entries, command_names
            raw = zf.read(name).decode("utf-8", errors="ignore")
    except Exception:
        return menu_entries, command_names
    seen_pairs: set[tuple[str, str]] = set()
    for line in raw.splitlines():
        row = line.strip()
        if not row or row.startswith("#"):
            continue
        # Typical format: Menu>Path, "Command Name", class.path
        parts = [p.strip() for p in row.split(",")]
        if len(parts) < 2:
            continue
        menu = parts[0]
        command = parts[1].strip().strip('"')
        if not command or command == "-":
            continue
        pair = (menu, command)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        menu_entries.append(menu)
        command_names.append(command)
    return menu_entries, command_names

def _parse_execution_manifest(payload: dict) -> PluginExecutionManifest | None:
    """Parse execution manifest for the current workflow."""
    plugin_obj = payload.get("plugin")
    if not isinstance(plugin_obj, dict):
        return None
    identity = plugin_obj.get("identity", {})
    invocation = plugin_obj.get("invocation", {})
    io_contract = plugin_obj.get("io_contract", {})
    execution = plugin_obj.get("execution_mode", {})
    params_obj = plugin_obj.get("parameters", [])
    schema_obj = plugin_obj.get("schema", {})
    if not isinstance(identity, dict) or not isinstance(invocation, dict):
        return None
    plugin_id = _slug(str(identity.get("id", "")))
    if not plugin_id:
        return None
    impl_type = str(identity.get("implementation_type", "legacy_plugin"))
    if impl_type not in VALID_IMPL_TYPES:
        raise ValueError(f"Invalid implementation_type in manifest: {impl_type}")
    run_command = str(invocation.get("run_command", "")).strip()
    if not run_command:
        raise ValueError("Manifest must define invocation.run_command.")
    arg_builder = str(invocation.get("arg_builder", "ij_kv")).strip() or "ij_kv"
    parsed_params: list = []
    if isinstance(params_obj, list):
        for row in params_obj:
            if not isinstance(row, dict):
                continue
            p_type = str(row.get("type", "string")).strip()
            if p_type not in VALID_PARAM_TYPES:
                raise ValueError(f"Invalid parameter type '{p_type}' for plugin '{plugin_id}'.")
            parsed_params.append(
                ManifestParameter(
                    name=str(row.get("name", "")).strip(),
                    type=p_type,
                    default=row.get("default"),
                    required=bool(row.get("required", False)),
                    minimum=_maybe_float(row.get("min")),
                    maximum=_maybe_float(row.get("max")),
                    choices=[str(v) for v in row.get("choices", [])] if isinstance(row.get("choices"), list) else [],
                    mutually_exclusive_with=[str(v) for v in row.get("mutually_exclusive_with", [])]
                    if isinstance(row.get("mutually_exclusive_with"), list)
                    else [])
            )
    ui_dialog = str(execution.get("ui_dialog", "none"))
    threading = str(execution.get("threading", "worker_thread"))
    if ui_dialog not in VALID_UI_DIALOG:
        raise ValueError(f"Invalid ui_dialog in manifest: {ui_dialog}")
    if threading not in VALID_THREADING:
        raise ValueError(f"Invalid threading in manifest: {threading}")
    return PluginExecutionManifest(
        id=plugin_id,
        display_name=str(identity.get("display_name", plugin_id)),
        menu_path=str(identity.get("menu_path", "")),
        implementation_type=impl_type,
        run_command=run_command,
        arg_builder=arg_builder,
        arg_template=str(invocation.get("arg_template", "")),
        macro_template=str(invocation.get("macro_template", "")),
        parameters=[p for p in parsed_params if p.name],
        active_image_required=bool(io_contract.get("active_image_required", True)),
        roi_optional=bool(io_contract.get("roi_optional", True)),
        stack_required=bool(io_contract.get("stack_required", False)),
        outputs=dict(io_contract.get("outputs", {})) if isinstance(io_contract.get("outputs", {}), dict) else {},
        ui_dialog=ui_dialog,
        threading=threading,
        plugin_version_tested=str(schema_obj.get("plugin_version_tested", "")).strip(),
        csv_schema_version=str(schema_obj.get("csv_schema_version", "")).strip(),
        required_columns=[str(v).strip() for v in schema_obj.get("required_columns", [])]
        if isinstance(schema_obj.get("required_columns"), list)
        else [],
        optional_columns=[str(v).strip() for v in schema_obj.get("optional_columns", [])]
        if isinstance(schema_obj.get("optional_columns"), list)
        else [],
        csv_separator=str(schema_obj.get("separator", ",") or ","),
        csv_decimal=str(schema_obj.get("decimal", ".") or "."))

def _coerce_value(spec: ManifestParameter, value: Any) -> Any:
    """Handle the coerce value helper flow."""
    if spec.type == "int":
        return int(value)
    if spec.type == "float":
        return float(value)
    if spec.type == "bool":
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        return s in {"1", "true", "yes", "on"}
    if spec.type in {"choice", "string"}:
        return str(value)
    return value

def _maybe_float(value: Any) -> float | None:
    """Handle the maybe float helper flow."""
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None

def _as_arg_value(value: Any) -> str:
    """Handle the as arg value helper flow."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)

def _escape_macro(value: str) -> str:
    """Handle the escape macro helper flow."""
    return str(value).replace("\\", "\\\\").replace("\"", "\\\"")
