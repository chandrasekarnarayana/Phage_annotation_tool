"""Metadata extraction for TIFF/OME/Micro-Manager images."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import tifffile as tif


@dataclass
class MetadataBundle:
    """Container for raw and parsed metadata."""

    summary: Dict[str, Any]
    tiff_tags: Dict[str, Any]
    ome_xml: Optional[str]
    ome_parsed: Optional[Dict[str, Any]]
    micromanager: Optional[Dict[str, Any]]
    vendor_private: Dict[str, Any]


def read_metadata(path: str) -> MetadataBundle:
    """Read metadata for a TIFF/OME-TIFF without loading pixel data."""
    with tif.TiffFile(path) as tf:
        series = tf.series[0]
        page = series.pages[0] if series.pages else tf.pages[0]
        tiff_tags = {tag.name: tag.value for tag in page.tags.values()}
        ome_xml = tf.ome_metadata
        ome_parsed = _parse_ome_metadata(ome_xml) if ome_xml else None
        micromanager = _parse_micromanager(tf, tiff_tags)
        vendor_private = _extract_vendor_private(page.tags)
        summary = _build_summary(series, ome_parsed, micromanager)
    return MetadataBundle(
        summary=summary,
        tiff_tags=tiff_tags,
        ome_xml=ome_xml,
        ome_parsed=ome_parsed,
        micromanager=micromanager,
        vendor_private=vendor_private,
    )


def read_metadata_summary(path: str) -> Dict[str, Any]:
    """Read a summary metadata dict without parsing full raw tags."""
    with tif.TiffFile(path) as tf:
        series = tf.series[0]
        ome_parsed = _parse_ome_metadata(tf.ome_metadata) if tf.ome_metadata else None
        micromanager = _parse_micromanager(tf, {})
        summary = _build_summary(series, ome_parsed, micromanager)
    return summary


def _build_summary(
    series: tif.TiffSeries,
    ome_parsed: Optional[Dict[str, Any]],
    mm: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    axes = series.axes
    shape = series.shape
    dims = _axes_to_tzyx(axes, shape)
    summary: Dict[str, Any] = {
        "axes": axes,
        "shape": tuple(shape),
        "dims": {"T": dims[0], "Z": dims[1], "Y": dims[2], "X": dims[3]},
        "dtype": str(series.dtype),
    }
    if ome_parsed:
        summary["ome"] = ome_parsed
        pixel = ome_parsed.get("pixel_size_um")
        if pixel:
            summary["pixel_size_um"] = pixel
    if mm and "summary" in mm:
        summary["micromanager"] = mm.get("summary")
        if "PixelSize_um" in mm.get("summary", {}):
            summary["pixel_size_um"] = mm["summary"]["PixelSize_um"]
    if ome_parsed and ome_parsed.get("acquisition_time"):
        summary["acquisition_time"] = ome_parsed["acquisition_time"]
    return summary


def _axes_to_tzyx(axes: str, shape: Tuple[int, ...]) -> Tuple[int, int, int, int]:
    axes = axes.upper()
    mapping = dict(zip(axes, shape))
    return (
        int(mapping.get("T", 1)),
        int(mapping.get("Z", 1)),
        int(mapping.get("Y", shape[-2])),
        int(mapping.get("X", shape[-1])),
    )


def _parse_ome_metadata(ome_xml: Optional[str]) -> Optional[Dict[str, Any]]:
    if not ome_xml:
        return None
    try:
        root = ET.fromstring(ome_xml)
    except ET.ParseError:
        return None
    ns = {"ome": "http://www.openmicroscopy.org/Schemas/OME/2016-06"}
    pixels = root.find(".//ome:Pixels", ns)
    if pixels is None:
        return None
    parsed: Dict[str, Any] = {
        "dimension_order": pixels.get("DimensionOrder"),
        "size_t": _int_or_none(pixels.get("SizeT")),
        "size_z": _int_or_none(pixels.get("SizeZ")),
        "size_y": _int_or_none(pixels.get("SizeY")),
        "size_x": _int_or_none(pixels.get("SizeX")),
        "type": pixels.get("Type"),
    }
    px_x = _float_or_none(pixels.get("PhysicalSizeX"))
    px_y = _float_or_none(pixels.get("PhysicalSizeY"))
    px_z = _float_or_none(pixels.get("PhysicalSizeZ"))
    if px_x is not None or px_y is not None:
        parsed["pixel_size_um"] = {"x": px_x, "y": px_y, "z": px_z}
    channels = []
    for chan in pixels.findall(".//ome:Channel", ns):
        channels.append(
            {
                "name": chan.get("Name"),
                "samples": _int_or_none(chan.get("SamplesPerPixel")),
            }
        )
    if channels:
        parsed["channels"] = channels
    image = root.find(".//ome:Image", ns)
    if image is not None and image.get("AcquisitionDate"):
        parsed["acquisition_time"] = image.get("AcquisitionDate")
    return parsed


def _parse_micromanager(tf: tif.TiffFile, tags: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        mm = getattr(tf, "micromanager_metadata", None)
        if mm:
            return {"summary": mm.get("Summary"), "metadata": mm}
    except Exception:
        pass
    desc = tags.get("ImageDescription")
    if isinstance(desc, str):
        try:
            data = json.loads(desc)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and ("Summary" in data or "Micro-Manager" in desc):
            return {"summary": data.get("Summary"), "metadata": data}
    return None


def _extract_vendor_private(tags: tif.TiffTags) -> Dict[str, Any]:
    vendor: Dict[str, Any] = {}
    for tag in tags.values():
        if tag.code >= 65000 or tag.name.lower().startswith("unknown"):
            vendor[tag.name] = tag.value
    return vendor


def _int_or_none(value: Optional[str]) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _float_or_none(value: Optional[str]) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None
