"""Parse and format annotation metadata from filenames and files."""

from __future__ import annotations

import json
import pathlib
import re
from typing import Dict, Optional

_ANN_MARKER = "__ann__"
_ROI_RE = re.compile(r"^(box|circle)\((.*)\)$", re.IGNORECASE)


def parse_filename_tokens(path: pathlib.Path) -> Dict[str, object]:
    """Parse annotation metadata tokens embedded in a filename."""
    stem = path.stem
    if _ANN_MARKER not in stem:
        return {}
    token_str = stem.split(_ANN_MARKER, 1)[1]
    tokens = [t for t in token_str.split("__") if t]
    meta: Dict[str, object] = {}
    extra: Dict[str, str] = {}
    for token in tokens:
        if "=" not in token:
            extra[token] = ""
            continue
        key, value = token.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "roi":
            roi = _parse_roi(value)
            if roi:
                meta["roi"] = roi
            else:
                extra[key] = value
        elif key == "crop":
            rect = _parse_rect(value)
            if rect:
                meta["crop"] = rect
            else:
                extra[key] = value
        elif key == "win":
            vals = _parse_pair(value)
            if vals:
                meta.setdefault("display", {})["win"] = {"min": vals[0], "max": vals[1]}
            else:
                extra[key] = value
        elif key == "pct":
            vals = _parse_pair(value)
            if vals:
                meta.setdefault("display", {})["pct"] = {
                    "low": vals[0],
                    "high": vals[1],
                }
            else:
                extra[key] = value
        elif key == "gamma":
            try:
                meta.setdefault("display", {})["gamma"] = float(value)
            except ValueError:
                extra[key] = value
        elif key == "lut":
            meta.setdefault("display", {})["lut"] = value
        elif key == "axis":
            meta["axis"] = value
        elif key == "src":
            meta["source"] = value
        else:
            extra[key] = value
    if extra:
        meta.setdefault("extra", {}).update(extra)
    return meta


def parse_csv_header_meta(path: pathlib.Path) -> Dict[str, object]:
    """Parse metadata JSON from CSV comment headers."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.startswith("#"):
                    break
                if line.startswith("# phage_annotator:"):
                    payload = line.split(":", 1)[1].strip()
                    return json.loads(payload)
    except (OSError, json.JSONDecodeError):
        return {}
    return {}


def parse_json_meta(path: pathlib.Path) -> Dict[str, object]:
    """Parse metadata from a JSON annotation file."""
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(data, dict) and "meta" in data:
        meta = data.get("meta")
        return meta if isinstance(meta, dict) else {}
    return {}


def merge_meta(file_meta: Dict[str, object], name_meta: Dict[str, object]) -> Dict[str, object]:
    """Merge metadata dicts, preferring file metadata."""
    merged = dict(name_meta)
    _merge_dict(merged, file_meta)
    return merged


def format_tokens(meta: Dict[str, object]) -> str:
    """Format metadata into filename tokens (without extension)."""
    tokens = []
    roi = meta.get("roi")
    if isinstance(roi, dict):
        shape = roi.get("shape")
        if shape == "box":
            rect = roi.get("rect")
            if rect:
                tokens.append(f"roi=box({','.join(_fmt_num(v) for v in rect)})")
        elif shape == "circle":
            center = roi.get("center")
            radius = roi.get("radius")
            if center and radius is not None:
                tokens.append(f"roi=circle({','.join(_fmt_num(v) for v in (*center, radius))})")
    crop = meta.get("crop")
    if crop:
        tokens.append(f"crop={','.join(_fmt_num(v) for v in crop)}")
    display = meta.get("display")
    if isinstance(display, dict):
        win = display.get("win")
        if isinstance(win, dict):
            tokens.append(f"win={_fmt_num(win.get('min'))},{_fmt_num(win.get('max'))}")
        pct = display.get("pct")
        if isinstance(pct, dict):
            tokens.append(f"pct={_fmt_num(pct.get('low'))},{_fmt_num(pct.get('high'))}")
        if "gamma" in display:
            tokens.append(f"gamma={_fmt_num(display.get('gamma'))}")
        if "lut" in display:
            tokens.append(f"lut={display.get('lut')}")
    if "axis" in meta:
        tokens.append(f"axis={meta['axis']}")
    if "source" in meta:
        tokens.append(f"src={meta['source']}")
    extra = meta.get("extra")
    if isinstance(extra, dict):
        for key, val in extra.items():
            if val == "":
                tokens.append(str(key))
            else:
                tokens.append(f"{key}={val}")
    if not tokens:
        return ""
    return _ANN_MARKER + "__".join(tokens)


def _parse_roi(value: str) -> Optional[Dict[str, object]]:
    match = _ROI_RE.match(value)
    if not match:
        return None
    kind = match.group(1).lower()
    body = match.group(2)
    parts = _parse_list(body)
    if kind == "box" and len(parts) == 4:
        return {"shape": "box", "rect": tuple(parts)}
    if kind == "circle" and len(parts) == 3:
        return {"shape": "circle", "center": (parts[0], parts[1]), "radius": parts[2]}
    return None


def _parse_rect(value: str) -> Optional[tuple[float, float, float, float]]:
    parts = _parse_list(value)
    if len(parts) != 4:
        return None
    return tuple(parts)  # type: ignore[return-value]


def _parse_pair(value: str) -> Optional[tuple[float, float]]:
    parts = _parse_list(value)
    if len(parts) != 2:
        return None
    return (parts[0], parts[1])


def _parse_list(value: str) -> list[float]:
    parts = []
    for chunk in value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            parts.append(float(chunk))
        except ValueError:
            return []
    return parts


def _merge_dict(base: Dict[str, object], update: Dict[str, object]) -> None:
    for key, val in update.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _merge_dict(base[key], val)  # type: ignore[arg-type]
        else:
            base[key] = val


def _fmt_num(val: object) -> str:
    if val is None:
        return ""
    if isinstance(val, float):
        return f"{val:.4f}".rstrip("0").rstrip(".")
    return str(val)
