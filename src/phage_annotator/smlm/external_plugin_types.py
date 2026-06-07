"""Smlm external plugin types helpers for the phage annotation tool.

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


VALID_PARAM_TYPES = {"int", "float", "bool", "choice", "string"}
VALID_IMPL_TYPES = {"legacy_plugin", "plugin_filter", "extended_filter", "scijava_command"}
VALID_UI_DIALOG = {"none", "native", "scripted"}
VALID_THREADING = {"ui_thread", "worker_thread"}



@dataclass(frozen=True)
class ManifestParameter:
    """Typed plugin parameter specification."""

    name: str
    type: str
    default: Any = None
    required: bool = False
    minimum: float | None = None
    maximum: float | None = None
    choices: List[str] = field(default_factory=list)
    mutually_exclusive_with: List[str] = field(default_factory=list)

@dataclass(frozen=True)
class PluginExecutionManifest:
    """Strict plugin execution contract."""

    id: str
    display_name: str
    menu_path: str
    implementation_type: str
    run_command: str
    arg_builder: str = "ij_kv"
    arg_template: str = ""
    macro_template: str = ""
    parameters: List[ManifestParameter] = field(default_factory=list)
    active_image_required: bool = True
    roi_optional: bool = True
    stack_required: bool = False
    outputs: Dict[str, Any] = field(default_factory=dict)
    ui_dialog: str = "none"
    threading: str = "worker_thread"
    plugin_version_tested: str = ""
    csv_schema_version: str = ""
    required_columns: List[str] = field(default_factory=list)
    optional_columns: List[str] = field(default_factory=list)
    csv_separator: str = ","
    csv_decimal: str = "."

@dataclass(frozen=True)
class ExternalFijiPlugin:
    """Descriptor for an external Fiji plugin artifact."""

    plugin_id: str
    name: str
    jar_path: str
    macro_path: str = ""
    manifest_path: str = ""
    manifest: PluginExecutionManifest | None = None
    menu_entries: List[str] = field(default_factory=list)
    command_names: List[str] = field(default_factory=list)
    description: str = ""
    env: Dict[str, str] = field(default_factory=dict)
    ui_visible: bool = True

def discover_external_fiji_plugins(start_dir: Optional[Path] = None) -> List[ExternalFijiPlugin]:
    """Discover plugin descriptors from `external_plugins` folder.

    Supports:
    - `*.jar` direct discovery
    - optional JSON manifests (`*.json`) with plugin metadata
    """
    root = Path(start_dir) if start_dir is not None else Path.cwd()
    plugin_dir = root if root.name == "external_plugins" else root / "external_plugins"
    if plugin_dir is None or not plugin_dir.exists():
        return []
    from phage_annotator.smlm.external_plugin_macros import (
        _parse_execution_manifest,
        _slug,
        parse_plugins_config_from_jar,
    )

    manifests = sorted(plugin_dir.glob("*.json"))
    by_id: Dict[str, ExternalFijiPlugin] = {}
    manifest_jar_paths: set[str] = set()
    for manifest in manifests:
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        parsed_manifest = _parse_execution_manifest(payload)
        jar = str(payload.get("jar_path", "")).strip()
        if parsed_manifest is not None and not jar:
            # strict manifest supports plugin.jar_path as canonical location
            jar = str(payload.get("plugin", {}).get("jar_path", "")).strip()
        if jar and not Path(jar).is_absolute():
            jar = str((plugin_dir / jar).resolve())
        if not jar:
            continue
        manifest_id = parsed_manifest.id if parsed_manifest is not None else ""
        plugin_id = _slug(str(payload.get("plugin_id", "")) or manifest_id or Path(jar).stem)
        if not plugin_id:
            continue
        macro = str(payload.get("macro_path", "")).strip()
        if parsed_manifest is not None and not macro:
            macro = str(payload.get("plugin", {}).get("macro_path", "")).strip()
        if macro and not Path(macro).is_absolute():
            macro = str((plugin_dir / macro).resolve())
        env = payload.get("env", {})
        if parsed_manifest is not None and not env:
            env = payload.get("plugin", {}).get("env", {})
        if not isinstance(env, dict):
            env = {}
        by_id[plugin_id] = ExternalFijiPlugin(
            plugin_id=plugin_id,
            name=str(
                payload.get("name")
                or (parsed_manifest.display_name if parsed_manifest is not None else Path(jar).stem)
            ),
            jar_path=str(Path(jar).resolve()),
            macro_path=macro,
            manifest_path=str(manifest.resolve()),
            manifest=parsed_manifest,
            menu_entries=[],
            command_names=[],
            description=str(payload.get("description", "")),
            env={str(k): str(v) for k, v in env.items()},
            ui_visible=bool(payload.get("ui_visible", True)))
        manifest_jar_paths.add(str(Path(jar).resolve()))

    for jar in sorted(plugin_dir.glob("*.jar")):
        jar_resolved = str(jar.resolve())
        if jar_resolved in manifest_jar_paths:
            continue
        plugin_id = _slug(jar.stem)
        if plugin_id in by_id:
            continue
        by_id[plugin_id] = ExternalFijiPlugin(
            plugin_id=plugin_id,
            name=jar.stem.replace("_", " "),
            jar_path=jar_resolved,
            menu_entries=[],
            command_names=[],
            ui_visible=True)
    # Enrich with plugins.config metadata when present.
    for pid, plugin in list(by_id.items()):
        menu_entries, command_names = parse_plugins_config_from_jar(plugin.jar_path)
        by_id[pid] = ExternalFijiPlugin(
            plugin_id=plugin.plugin_id,
            name=plugin.name,
            jar_path=plugin.jar_path,
            macro_path=plugin.macro_path,
            manifest_path=plugin.manifest_path,
            manifest=plugin.manifest,
            menu_entries=menu_entries,
            command_names=command_names,
            description=plugin.description,
            env=plugin.env,
            ui_visible=plugin.ui_visible)
    return sorted(by_id.values(), key=lambda p: p.plugin_id)

def plugin_map(start_dir: Optional[Path] = None) -> Dict[str, ExternalFijiPlugin]:
    """Build map of plugin id -> descriptor."""
    return {p.plugin_id: p for p in discover_external_fiji_plugins(start_dir=start_dir)}

def resolve_plugin_jar(
    plugin_id: str,
    selected_jar_path: str,
    *,
    start_dir: Optional[Path] = None) -> str:
    """Resolve effective plugin jar path from selection and overrides."""
    manual = (selected_jar_path or "").strip()
    if manual:
        return manual
    pmap = plugin_map(start_dir=start_dir)
    selected = pmap.get((plugin_id or "").strip().lower())
    if selected is None:
        return ""
    return selected.jar_path

def resolve_plugin_descriptor(
    plugin_id: str,
    *,
    start_dir: Optional[Path] = None) -> Optional[ExternalFijiPlugin]:
    """Resolve descriptor for selected plugin id."""
    pid = (plugin_id or "").strip().lower()
    if not pid:
        return None
    return plugin_map(start_dir=start_dir).get(pid)

def build_plugin_arg_string(plugin: ExternalFijiPlugin, params: Dict[str, Any]) -> str:
    """Build Fiji argument string from strict manifest definition."""
    from phage_annotator.smlm.external_plugin_macros import _as_arg_value

    manifest = plugin.manifest
    if manifest is None:
        # Backward-compat fallback: simple key=value join.
        return " ".join(f"{k}={_as_arg_value(v)}" for k, v in sorted(params.items()))
    clean = validate_plugin_parameters(manifest, params)
    if manifest.arg_builder == "template" and manifest.arg_template:
        return manifest.arg_template.format(**clean)
    if manifest.arg_builder == "json":
        return json.dumps(clean, sort_keys=True)
    return " ".join(f"{name}={_as_arg_value(clean[name])}" for name in clean.keys())

def validate_plugin_parameters(manifest: PluginExecutionManifest, params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate/coerce typed plugin parameters."""
    from phage_annotator.smlm.external_plugin_macros import _coerce_value

    clean: Dict[str, Any] = {}
    param_specs = {p.name: p for p in manifest.parameters}
    for name, spec in param_specs.items():
        val = params.get(name, spec.default)
        if val is None and spec.required:
            raise ValueError(f"Missing required plugin parameter: {name}")
        if val is None:
            continue
        coerced = _coerce_value(spec, val)
        if spec.minimum is not None and isinstance(coerced, (int, float)) and coerced < spec.minimum:
            raise ValueError(f"Parameter '{name}' below minimum ({spec.minimum}).")
        if spec.maximum is not None and isinstance(coerced, (int, float)) and coerced > spec.maximum:
            raise ValueError(f"Parameter '{name}' above maximum ({spec.maximum}).")
        if spec.choices and str(coerced) not in set(spec.choices):
            raise ValueError(f"Parameter '{name}' must be one of {spec.choices}.")
        clean[name] = coerced
    for name, spec in param_specs.items():
        if name not in clean:
            continue
        for other in spec.mutually_exclusive_with:
            if other in clean and clean[other] is not None:
                raise ValueError(f"Parameters '{name}' and '{other}' are mutually exclusive.")
    # Include pass-through extras for forward compatibility.
    for key, value in params.items():
        if key not in clean and key not in param_specs:
            clean[key] = value
    return clean
