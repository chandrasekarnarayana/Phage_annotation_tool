"""Annotation file indexing and matching helpers.

This module builds a lightweight index of annotation files near a folder of
images. It does not parse annotation content. Matching is based on a normalized
image basename and common filename suffix conventions (annotations, locs, etc.).
"""

from __future__ import annotations

import dataclasses
import pathlib
import re
from typing import Dict, Iterable, List

ANNOTATION_SUFFIXES = (".csv", ".json")

_TOKEN_RE = re.compile(r"([._-])(t|z|c|ch|frame|f)\d+$", re.IGNORECASE)


@dataclasses.dataclass(frozen=True)
class AnnotationIndexEntry:
    """Metadata about an annotation file on disk."""

    path: pathlib.Path
    size_bytes: int
    mtime: float


def build_index(folder: pathlib.Path) -> Dict[str, List[AnnotationIndexEntry]]:
    """Scan a folder and index annotation files by normalized basename."""
    index: Dict[str, List[AnnotationIndexEntry]] = {}
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in ANNOTATION_SUFFIXES:
            continue
        base_candidates = _annotation_base_candidates(path.name)
        entry = AnnotationIndexEntry(path=path, size_bytes=path.stat().st_size, mtime=path.stat().st_mtime)
        for base in base_candidates:
            index.setdefault(base, []).append(entry)
    return index


def match(image_path: pathlib.Path, index: Dict[str, List[AnnotationIndexEntry]]) -> List[AnnotationIndexEntry]:
    """Return annotation entries that match an image path."""
    base = _normalize_image_basename(image_path)
    return list(index.get(base, []))


def _normalize_image_basename(image_path: pathlib.Path) -> str:
    name = image_path.name
    if name.lower().endswith(".ome.tif") or name.lower().endswith(".ome.tiff"):
        stem = pathlib.Path(name[:-8]).stem
    else:
        stem = image_path.stem
    stem = _strip_tokens(stem)
    return _normalize_base(stem)


def _annotation_base_candidates(filename: str) -> Iterable[str]:
    stem = pathlib.Path(filename).stem
    if "__ann__" in stem:
        stem = stem.split("__ann__", 1)[0]
    stem = _strip_tokens(stem)
    stem = _strip_annotation_suffixes(stem)
    if stem.lower().endswith(".tif") or stem.lower().endswith(".tiff"):
        stem = pathlib.Path(stem).stem
    yield _normalize_base(stem)


def _strip_tokens(name: str) -> str:
    """Remove embedded metadata tokens like _t001, _z02, _c0."""
    out = name
    while True:
        new = _TOKEN_RE.sub("", out)
        if new == out:
            break
        out = new
    return out


def _strip_annotation_suffixes(name: str) -> str:
    lowered = name.lower()
    for suffix in ("annotations", "annotation", "thunderstorm", "locs", "localizations"):
        for sep in ("_", "-", "."):
            token = f"{sep}{suffix}"
            if lowered.endswith(token):
                return name[: -len(token)]
    return name


def _normalize_base(name: str) -> str:
    cleaned = name.strip().strip("._- ")
    return cleaned.lower()
