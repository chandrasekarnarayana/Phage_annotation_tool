"""SMLM back-end discovery helpers.

Locates external resources needed by the Fiji bridge:

* Bundled ThunderSTORM JAR files shipped inside the project tree
* Fiji/ImageJ installations on the host operating system

Platform-specific executable layout is handled by :mod:`.platform_utils`.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from phage_annotator.smlm.platform_utils import (
    discover_fiji_executable,
    fiji_app_to_executable,
)


def discover_bundled_thunderstorm_jar(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Locate a bundled ThunderSTORM JAR in common project locations.

    Searches for ``Thunder_STORM.jar`` (and common alternative spellings) under
    the ``external_plugins/`` directory relative to the repository root and any
    caller-specified *start_dir*.

    Returns the resolved :class:`~pathlib.Path` of the first match, or *None*
    if no JAR is found.
    """
    candidates = ("Thunder_STORM.jar", "ThunderSTORM.jar", "thunder_storm.jar")
    roots: List[Path] = []
    if start_dir is not None:
        roots.append(Path(start_dir))
    roots.append(Path.cwd())
    # src/phage_annotator/smlm/backends_discovery.py → repo root is parents[3]
    roots.append(Path(__file__).resolve().parents[3])
    for root in roots:
        plugin_dir = root / "external_plugins"
        for name in candidates:
            jar = plugin_dir / name
            if jar.exists() and jar.is_file():
                return jar.resolve()
    return None


def discover_thunderstorm_jar_in_fiji(fiji_app_path: str) -> Optional[str]:
    """Search for ThunderSTORM JAR inside a Fiji.app installation.

    Fiji installs plugins under ``<Fiji.app>/plugins/``.  This function
    searches that directory tree for a ThunderSTORM JAR.

    Parameters
    ----------
    fiji_app_path:
        Path to the ``Fiji.app`` directory (e.g. ``/Applications/Fiji.app``).

    Returns the JAR path as a string, or *None* if not found.
    """
    app = Path(fiji_app_path).expanduser().resolve()
    if not app.exists():
        return None
    candidates = (
        "Thunder_STORM.jar",
        "ThunderSTORM.jar",
        "thunder_storm.jar",
        "thunderstorm.jar",
    )
    for plugin_dir in (app / "plugins", app / "jars"):
        if not plugin_dir.is_dir():
            continue
        for name in candidates:
            jar = plugin_dir / name
            if jar.exists() and jar.is_file():
                return str(jar.resolve())
        # Some distributions place the JAR one level deeper
        for child in plugin_dir.iterdir():
            if child.is_dir():
                for name in candidates:
                    jar = child / name
                    if jar.exists() and jar.is_file():
                        return str(jar.resolve())
    return None


def auto_discover_fiji(extra_dirs: Optional[List[str]] = None) -> Optional[str]:
    """Attempt to locate the Fiji executable on the current system.

    Wraps :func:`.platform_utils.discover_fiji_executable` and additionally
    checks any caller-supplied *extra_dirs*.

    Returns the executable path, or *None* if Fiji is not found.
    """
    return discover_fiji_executable(extra_dirs=extra_dirs or [])


def auto_discover_thunderstorm_jar(fiji_exe: Optional[str] = None) -> Optional[str]:
    """Locate a ThunderSTORM JAR using all available search strategies.

    Search order:

    1. ``<fiji_app>/plugins/`` — installed inside Fiji
    2. Project ``external_plugins/`` tree (bundled fallback)

    If *fiji_exe* is provided the function will attempt to derive the Fiji.app
    root from the executable path and search its plugins directory first.

    Returns the JAR path as a string, or *None* if not found.
    """
    # 1. Derive Fiji.app root from executable path and search plugins
    if fiji_exe:
        exe_path = Path(fiji_exe).resolve()
        # Walk up from executable to find the Fiji.app root
        for parent in exe_path.parents:
            jar = discover_thunderstorm_jar_in_fiji(str(parent))
            if jar:
                return jar
            # Stop searching if we find a plugins/ directory (likely Fiji.app root)
            if (parent / "plugins").is_dir():
                break

    # 2. Fallback to project-bundled JAR
    bundled = discover_bundled_thunderstorm_jar()
    if bundled:
        return str(bundled)

    return None
