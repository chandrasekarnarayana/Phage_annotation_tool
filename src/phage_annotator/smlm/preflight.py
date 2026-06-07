"""Preflight checks for Fiji bridge execution."""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import numpy as np
from tifffile import imwrite

from phage_annotator.smlm.backends import ThunderstormBridgeConfig
from phage_annotator.smlm.external_plugins import (
    build_plugin_arg_string,
    resolve_plugin_descriptor,
    resolve_plugin_jar,
)


@dataclass(frozen=True)
class PreflightItem:
    """Single preflight check result."""

    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class PreflightReport:
    """Aggregate preflight report."""

    ok: bool
    exit_code: int = 0
    items: List[PreflightItem] = field(default_factory=list)

    def to_lines(self) -> List[str]:
        """Convert lines for the current workflow."""
        lines = []
        for item in self.items:
            status = "OK" if item.ok else "FAIL"
            lines.append(f"[{status}] {item.name}: {item.detail}")
        return lines


def run_preflight(config: ThunderstormBridgeConfig, *, probe: bool = False) -> PreflightReport:
    """Run deterministic preflight checks for configured backend."""
    backend = (config.backend or "internal").strip().lower()
    items: List[PreflightItem] = []
    exit_code = 0
    if backend == "internal":
        items.append(PreflightItem("Backend", True, "Internal backend requires no Fiji runtime."))
        return PreflightReport(ok=True, exit_code=0, items=items)

    plugin_jar = resolve_plugin_jar(
        config.plugin_id,
        config.plugin_jar_path or config.thunderstorm_jar_path,
    )
    plugin_desc = resolve_plugin_descriptor(config.plugin_id)

    if backend == "fiji_subprocess":
        exe = Path(config.fiji_executable) if config.fiji_executable else None
        if exe is None or not exe.exists():
            items.append(PreflightItem("Fiji executable", False, "Missing path."))
            exit_code = max(exit_code, 2)
        else:
            try:
                proc = subprocess.run(
                    [str(exe), "--headless", "-eval", "print(\"ok\");"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                ok = proc.returncode == 0
                detail = "Runnable." if ok else (proc.stderr.strip() or proc.stdout.strip() or f"exit={proc.returncode}")
                items.append(PreflightItem("Fiji executable", ok, detail))
                if not ok:
                    exit_code = max(exit_code, 2)
            except Exception as exc:
                items.append(PreflightItem("Fiji executable", False, str(exc)))
                exit_code = max(exit_code, 2)
    elif backend == "fiji_pyimagej":
        app = Path(config.pyimagej_app_path) if config.pyimagej_app_path else None
        if app is None or not app.exists():
            items.append(PreflightItem("PyImageJ app path", False, "Missing Fiji.app path."))
        else:
            items.append(PreflightItem("PyImageJ app path", True, str(app)))
        try:
            import imagej  # type: ignore  # noqa: F401

            items.append(PreflightItem("PyImageJ import", True, "imagej module available."))
        except Exception as exc:
            items.append(PreflightItem("PyImageJ import", False, str(exc)))

    fiji_missing = any(
        item.name in {"Fiji executable", "PyImageJ app path"} and not item.ok
        for item in items
    )

    if plugin_jar:
        jar_path = Path(plugin_jar)
        jar_ok = jar_path.exists()
        items.append(
            PreflightItem(
                "Plugin JAR",
                jar_ok,
                str(jar_path) if jar_ok else f"Missing: {jar_path}",
            )
        )
        if not jar_ok:
            if not fiji_missing:
                exit_code = max(exit_code, 3)
    else:
        items.append(PreflightItem("Plugin JAR", False, "No plugin JAR resolved."))
        if not fiji_missing:
            exit_code = max(exit_code, 3)

    if config.macro_path:
        macro = Path(config.macro_path)
        items.append(
            PreflightItem(
                "Macro path",
                macro.exists(),
                str(macro) if macro.exists() else f"Missing: {macro}",
            )
        )
    else:
        has_manifest = bool(plugin_desc is not None and plugin_desc.manifest is not None)
        items.append(
            PreflightItem(
                "Macro or manifest",
                has_manifest,
                "Manifest-based macro generation enabled." if has_manifest else "No macro path and no strict manifest.",
            )
        )
        if not has_manifest:
            if not fiji_missing:
                exit_code = max(exit_code, 4)

    try:
        with tempfile.NamedTemporaryFile(prefix="phage_preflight_", suffix=".tmp", delete=True) as tmp:
            tmp.write(b"ok")
            tmp.flush()
        items.append(PreflightItem("Output directory", True, "Writable temp directory."))
    except Exception as exc:
        items.append(PreflightItem("Output directory", False, str(exc)))

    if plugin_desc is not None:
        if plugin_desc.command_names:
            items.append(
                PreflightItem(
                    "plugins.config commands",
                    True,
                    ", ".join(plugin_desc.command_names[:3]) + ("..." if len(plugin_desc.command_names) > 3 else ""),
                )
            )
        else:
            items.append(PreflightItem("plugins.config commands", False, "No command entries discovered in JAR."))
            if not fiji_missing:
                exit_code = max(exit_code, 3)
    else:
        items.append(PreflightItem("Plugin descriptor", False, "Plugin id not discovered in external_plugins/."))
        if not fiji_missing:
            exit_code = max(exit_code, 3)

    if probe and backend == "fiji_subprocess":
        probe_item, probe_code = _run_probe(config, plugin_desc)
        items.append(probe_item)
        exit_code = max(exit_code, probe_code)

    ok = all(item.ok for item in items)
    if ok:
        exit_code = 0
    elif exit_code == 0:
        exit_code = 2
    return PreflightReport(ok=ok, exit_code=exit_code, items=items)


def _run_probe(config: ThunderstormBridgeConfig, plugin_desc):
    """Active probe: launch Fiji headless and ensure a marker file is produced."""
    exe = Path(config.fiji_executable) if config.fiji_executable else None
    if exe is None or not exe.exists():
        return PreflightItem("Probe", False, "Skipped: Fiji executable missing."), 2
    if plugin_desc is None:
        return PreflightItem("Probe", False, "Skipped: plugin descriptor missing."), 3
    command = ""
    arg_string = ""
    if plugin_desc.manifest is not None:
        command = plugin_desc.manifest.run_command
        defaults = {
            p.name: p.default for p in plugin_desc.manifest.parameters if p.default is not None and p.name
        }
        try:
            arg_string = build_plugin_arg_string(plugin_desc, defaults)
        except Exception:
            arg_string = ""
    elif plugin_desc.command_names:
        command = plugin_desc.command_names[0]
    if not command:
        return PreflightItem("Probe", False, "No callable plugin command discovered."), 3
    with tempfile.TemporaryDirectory(prefix="phage_probe_") as tmp_dir:
        tmp = Path(tmp_dir)
        input_tif = tmp / "probe_input.tif"
        probe_ok = tmp / "probe_ok.txt"
        macro = tmp / "probe.ijm"
        frame = (np.random.default_rng(1).normal(10.0, 1.0, size=(32, 32))).astype(np.float32)
        frame[16, 16] += 100.0
        imwrite(input_tif, frame)
        macro.write_text(
            (
                "setBatchMode(true);\n"
                f"open(\"{_escape_macro_path(str(input_tif))}\");\n"
                f"run(\"{_escape_macro(command)}\", \"{_escape_macro(arg_string)}\");\n"
                f"File.saveString(\"ok\", \"{_escape_macro_path(str(probe_ok))}\");\n"
            ),
            encoding="utf-8",
        )
        try:
            proc = subprocess.run(
                [str(exe), "--headless", "-macro", str(macro)],
                check=False,
                capture_output=True,
                text=True,
                timeout=max(30, int(config.timeout_sec)),
            )
        except Exception as exc:
            return PreflightItem("Probe", False, f"Fiji probe failed to launch: {exc}"), 2
        if proc.returncode != 0:
            detail = (proc.stderr or "").strip() or (proc.stdout or "").strip() or f"exit={proc.returncode}"
            return PreflightItem("Probe", False, f"Macro execution failed: {detail}"), 4
        if not probe_ok.exists():
            return PreflightItem("Probe", False, "Macro finished but probe output marker missing."), 5
    return PreflightItem("Probe", True, "Headless plugin invocation and marker output succeeded."), 0


def _escape_macro(value: str) -> str:
    """Handle the escape macro helper flow."""
    return str(value).replace("\\", "\\\\").replace("\"", "\\\"")


def _escape_macro_path(value: str) -> str:
    """Handle the escape macro path helper flow."""
    return _escape_macro(str(value))


def report_to_text(report: PreflightReport) -> str:
    """Format preflight report as multiline text."""
    return os.linesep.join(report.to_lines())
