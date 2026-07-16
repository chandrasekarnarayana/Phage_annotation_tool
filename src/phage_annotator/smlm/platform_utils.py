"""Cross-platform Fiji / ImageJ path resolution utilities.

Fiji is distributed as a self-contained application bundle. The executable
name and directory layout differ across operating systems:

  Linux  : ``Fiji.app/ImageJ-linux64``  (or ``ImageJ-linux32``)
  macOS  : ``Fiji.app/Contents/MacOS/ImageJ``
  Windows: ``Fiji.app\\Fiji.exe``

This module centralises all platform detection and path normalisation so
the rest of the SMLM bridge code remains platform-agnostic.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import List, Optional, Sequence


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

_SYSTEM = platform.system().lower()  # "linux", "darwin", "windows"


def is_linux() -> bool:
    return _SYSTEM == "linux"


def is_mac() -> bool:
    return _SYSTEM == "darwin"


def is_windows() -> bool:
    return _SYSTEM == "windows"


# ---------------------------------------------------------------------------
# Fiji executable resolution
# ---------------------------------------------------------------------------

def fiji_app_to_executable(fiji_app_path: str) -> Optional[str]:
    """Return the Fiji executable path given a ``Fiji.app`` directory path.

    Handles the platform-specific layout:

    * **Linux** : ``<fiji_app>/ImageJ-linux64``, ``ImageJ-linux32``
    * **macOS** : ``<fiji_app>/Contents/MacOS/ImageJ``
    * **Windows**: ``<fiji_app>\\Fiji.exe``

    Returns *None* if the executable cannot be found in the expected location.
    """
    app = Path(fiji_app_path).expanduser().resolve()
    if not app.exists():
        return None
    if is_mac():
        candidates = [
            app / "Contents" / "MacOS" / "ImageJ",
            app / "Contents" / "MacOS" / "Fiji",
        ]
    elif is_windows():
        candidates = [
            app / "Fiji.exe",
            app / "fiji.exe",
            app / "ImageJ.exe",
            app / "imagej.exe",
        ]
    else:  # Linux and other Unix-like
        machine = platform.machine().lower()
        arch = "64" if "64" in machine or "aarch64" in machine else "32"
        candidates = [
            app / f"ImageJ-linux{arch}",
            app / "ImageJ-linux64",
            app / "ImageJ-linux32",
            app / "ImageJ",
        ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def discover_fiji_executable(extra_dirs: Optional[Sequence[str]] = None) -> Optional[str]:
    """Attempt to locate the Fiji executable on the current system.

    Search order:
    1. ``FIJI_EXECUTABLE`` environment variable (direct path)
    2. ``FIJI_APP`` environment variable (path to ``Fiji.app`` directory)
    3. Platform-specific standard installation locations
    4. *extra_dirs* (caller-supplied paths to check)

    Returns the path to the Fiji binary, or *None* if not found.
    """
    # 1. Direct executable environment variable
    env_exec = os.environ.get("FIJI_EXECUTABLE", "").strip()
    if env_exec and Path(env_exec).exists():
        return env_exec

    # 2. Fiji.app directory via environment variable
    env_app = os.environ.get("FIJI_APP", "").strip()
    if env_app:
        exe = fiji_app_to_executable(env_app)
        if exe:
            return exe

    # 3. Standard platform locations
    app_dirs = _standard_fiji_app_locations()

    # 4. Extra caller-supplied directories
    if extra_dirs:
        app_dirs.extend([Path(d).expanduser() for d in extra_dirs if d])

    for app_dir in app_dirs:
        if app_dir.exists() and app_dir.is_dir():
            exe = fiji_app_to_executable(str(app_dir))
            if exe:
                return exe

    return None


def _standard_fiji_app_locations() -> List[Path]:
    """Return platform-specific standard Fiji.app installation directories.

    Includes both fixed known locations and glob-expanded paths under common
    user directories so that portable installations (e.g. in ``~/Downloads/``)
    are discovered automatically regardless of the exact sub-folder name.
    """
    home = Path.home()
    locs: List[Path] = []

    if is_mac():
        # Fixed standard locations
        locs = [
            Path("/Applications/Fiji.app"),
            home / "Applications" / "Fiji.app",
            home / "Desktop" / "Fiji.app",
            home / "fiji" / "Fiji.app",
            home / "Fiji.app",
        ]
        # Glob: any immediate sub-directory in ~/Downloads or ~/Desktop
        for parent in (home / "Downloads", home / "Desktop", home / "Applications"):
            locs.extend(_glob_fiji_app_dirs(parent))

    elif is_windows():
        program_files = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
            Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local"))),
        ]
        for pf in program_files:
            locs.extend([pf / "Fiji.app", pf / "Fiji", pf / "fiji"])
        locs.extend([
            home / "Desktop" / "Fiji.app",
            home / "Fiji.app",
            Path(r"C:\Fiji.app"),
            Path(r"C:\fiji"),
            Path(r"D:\Fiji.app"),
        ])
        # Glob portable installs in common user folders
        for parent in (home / "Downloads", home / "Desktop", home / "Documents"):
            locs.extend(_glob_fiji_app_dirs(parent))

    else:  # Linux / other Unix
        locs = [
            home / "Fiji.app",
            home / "fiji" / "Fiji.app",
            home / "bin" / "Fiji.app",
            Path("/opt/Fiji.app"),
            Path("/opt/fiji/Fiji.app"),
            Path("/usr/local/Fiji.app"),
            Path("/usr/local/fiji/Fiji.app"),
            Path("/usr/share/fiji/Fiji.app"),
        ]
        # Glob portable installs in ~/Downloads, ~/Desktop, ~/bin
        for parent in (home / "Downloads", home / "Desktop", home / "bin", home / "opt"):
            locs.extend(_glob_fiji_app_dirs(parent))

    # Remove duplicates while preserving order
    seen: set = set()
    unique: List[Path] = []
    for p in locs:
        key = str(p)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _glob_fiji_app_dirs(parent: Path) -> List[Path]:
    """Return all ``Fiji.app`` directories found one level below *parent*.

    Handles both direct ``parent/Fiji.app`` and portable bundles like
    ``parent/fiji-linux64-20250601/Fiji.app`` by searching all immediate
    sub-directories for a ``Fiji.app`` child.
    """
    found: List[Path] = []
    if not parent.is_dir():
        return found
    # Direct: ~/Downloads/Fiji.app
    direct = parent / "Fiji.app"
    if direct.is_dir():
        found.append(direct)
    # One level deep: ~/Downloads/<anything>/Fiji.app
    try:
        for child in parent.iterdir():
            if not child.is_dir():
                continue
            candidate = child / "Fiji.app"
            if candidate.is_dir():
                found.append(candidate)
    except PermissionError:
        pass
    return found


# ---------------------------------------------------------------------------
# Platform-aware subprocess command building
# ---------------------------------------------------------------------------

def split_command_template(template: str) -> List[str]:
    """Split a command template into a list of arguments, platform-safely.

    On Windows, ``shlex.split()`` treats ``\\`` as an escape character and
    will corrupt backslash-separated paths. This wrapper uses the correct
    POSIX flag for the current platform.
    """
    import shlex
    if is_windows():
        # posix=False preserves backslashes in Windows paths
        return shlex.split(template, posix=False)
    return shlex.split(template)


def build_fiji_headless_command(
    fiji_executable: str,
    macro_path: str,
    *,
    extra_args: Optional[Sequence[str]] = None,
) -> List[str]:
    """Build a platform-correct Fiji headless command list.

    Produces a command equivalent to running ThunderSTORM in headless mode via
    ``Fiji --headless --run <macro>``.  The result is a list suitable for
    :func:`subprocess.run` which avoids shell interpretation of paths with
    spaces or special characters.

    Parameters
    ----------
    fiji_executable:
        Full path to the Fiji binary (e.g. ``/Applications/Fiji.app/Contents/MacOS/ImageJ``).
    macro_path:
        Full path to the ``.ijm`` macro file.
    extra_args:
        Optional additional arguments appended to the command list.
    """
    cmd: List[str] = [fiji_executable, "--headless", "--console", f"--run={macro_path}"]
    if extra_args:
        cmd.extend(extra_args)
    return cmd


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def fiji_executable_placeholder() -> str:
    """Return a platform-appropriate placeholder for the Fiji executable path."""
    if is_mac():
        return "/Applications/Fiji.app/Contents/MacOS/ImageJ"
    if is_windows():
        return r"C:\Fiji.app\Fiji.exe"
    return "/opt/Fiji.app/ImageJ-linux64"


def fiji_app_placeholder() -> str:
    """Return a platform-appropriate placeholder for the Fiji.app directory."""
    if is_mac():
        return "/Applications/Fiji.app"
    if is_windows():
        return r"C:\Fiji.app"
    return "/opt/Fiji.app"


def thunderstorm_jar_placeholder() -> str:
    """Return a platform-appropriate placeholder for the ThunderSTORM JAR path."""
    if is_mac():
        return "/Applications/Fiji.app/plugins/Thunder_STORM.jar"
    if is_windows():
        return r"C:\Fiji.app\plugins\Thunder_STORM.jar"
    return "/opt/Fiji.app/plugins/Thunder_STORM.jar"


def pytorch_device_default() -> str:
    """Return the best available PyTorch compute device for the current platform.

    Priority:
    * ``cuda`` — NVIDIA GPU (Linux/Windows with CUDA-enabled PyTorch)
    * ``mps``  — Apple Silicon GPU (macOS M1/M2/M3)
    * ``cpu``  — Always available
    """
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if is_mac() and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"
