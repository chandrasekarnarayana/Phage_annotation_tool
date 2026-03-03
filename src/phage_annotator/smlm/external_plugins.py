"""Discovery, manifest parsing, and execution helpers for external Fiji plugins."""

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
    plugin_dir = _resolve_plugin_dir(start_dir)
    if plugin_dir is None or not plugin_dir.exists():
        return []
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
            ui_visible=bool(payload.get("ui_visible", True)),
        )
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
            ui_visible=True,
        )
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
            ui_visible=plugin.ui_visible,
        )
    return sorted(by_id.values(), key=lambda p: p.plugin_id)


def plugin_map(start_dir: Optional[Path] = None) -> Dict[str, ExternalFijiPlugin]:
    """Build map of plugin id -> descriptor."""
    return {p.plugin_id: p for p in discover_external_fiji_plugins(start_dir=start_dir)}


def resolve_plugin_jar(
    plugin_id: str,
    selected_jar_path: str,
    *,
    start_dir: Optional[Path] = None,
) -> str:
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
    start_dir: Optional[Path] = None,
) -> Optional[ExternalFijiPlugin]:
    """Resolve descriptor for selected plugin id."""
    pid = (plugin_id or "").strip().lower()
    if not pid:
        return None
    return plugin_map(start_dir=start_dir).get(pid)


def build_plugin_arg_string(plugin: ExternalFijiPlugin, params: Dict[str, Any]) -> str:
    """Build Fiji argument string from strict manifest definition."""
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
    parsed_params: List[ManifestParameter] = []
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
                    else [],
                )
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
        csv_decimal=str(schema_obj.get("decimal", ".") or "."),
    )


def _coerce_value(spec: ManifestParameter, value: Any) -> Any:
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
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _as_arg_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _escape_macro(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("\"", "\\\"")
