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


from phage_annotator.smlm.external_plugin_types import ManifestParameter, PluginExecutionManifest, ExternalFijiPlugin, discover_external_fiji_plugins, plugin_map, resolve_plugin_jar, resolve_plugin_descriptor, build_plugin_arg_string, validate_plugin_parameters
from phage_annotator.smlm.external_plugin_macros import build_manifest_macro, _resolve_plugin_dir, _slug, parse_plugins_config_from_jar, _parse_execution_manifest, _coerce_value, _maybe_float, _as_arg_value, _escape_macro
