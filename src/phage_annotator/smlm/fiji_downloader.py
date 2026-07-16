"""Download Fiji and ThunderSTORM JAR from the internet.

All downloads use only the Python standard library (``urllib``, ``zipfile``,
``tarfile``) so this module adds no extra runtime dependencies.

Typical usage from UI handlers::

    from phage_annotator.smlm.fiji_downloader import (
        download_fiji, install_thunderstorm_jar
    )

    exe = download_fiji(progress_cb=lambda done, total: ...)
    jar = install_thunderstorm_jar(fiji_exe="/path/to/ImageJ-linux64")
"""

from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path
from typing import Callable, Optional
from urllib.request import urlopen, Request

from phage_annotator.smlm.platform_utils import (
    is_linux,
    is_mac,
    is_windows,
    fiji_app_to_executable,
)

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

FIJI_DOWNLOAD_URLS: dict[str, str] = {
    "linux": "https://downloads.imagej.net/fiji/latest/fiji-linux64.zip",
    "darwin": "https://downloads.imagej.net/fiji/latest/fiji-macosx.zip",
    "windows": "https://downloads.imagej.net/fiji/latest/fiji-win64.zip",
}

THUNDERSTORM_JAR_URL = (
    "https://github.com/zitmen/thunderstorm/releases/download/v1.3/Thunder_STORM.jar"
)

ProgressCB = Callable[[int, int], None]


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_fiji_download_url() -> str:
    """Return the Fiji download URL for the current platform."""
    if is_mac():
        return FIJI_DOWNLOAD_URLS["darwin"]
    if is_windows():
        return FIJI_DOWNLOAD_URLS["windows"]
    return FIJI_DOWNLOAD_URLS["linux"]


def get_thunderstorm_download_url() -> str:
    """Return the ThunderSTORM JAR download URL."""
    return THUNDERSTORM_JAR_URL


def get_default_fiji_install_dir() -> Path:
    """Return the per-user application data directory for Fiji.

    * Linux  : ``~/.local/share/phage-annotator/fiji``
    * macOS  : ``~/Library/Application Support/phage-annotator/fiji``
    * Windows: ``%APPDATA%\\phage-annotator\\fiji``
    """
    if is_mac():
        base = Path.home() / "Library" / "Application Support"
    elif is_windows():
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    else:
        xdg = os.environ.get("XDG_DATA_HOME", "")
        base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "phage-annotator" / "fiji"


def get_default_thunderstorm_dir() -> Path:
    """Return the directory where a standalone ThunderSTORM JAR is stored."""
    if is_mac():
        base = Path.home() / "Library" / "Application Support"
    elif is_windows():
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    else:
        xdg = os.environ.get("XDG_DATA_HOME", "")
        base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "phage-annotator" / "thunderstorm"


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

_CHUNK = 65536  # 64 KiB read chunks


def download_with_progress(
    url: str,
    dest_path: Path,
    progress_cb: Optional[ProgressCB] = None,
    *,
    timeout: int = 60,
) -> None:
    """Stream *url* to *dest_path*, calling *progress_cb(bytes_done, total)*.

    *total* is -1 when the server does not send ``Content-Length``.
    Raises ``OSError`` or ``urllib.error.URLError`` on network failure.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": "phage-annotator/1.1.0"})
    with urlopen(req, timeout=timeout) as resp:
        total = int(resp.headers.get("Content-Length", -1))
        done = 0
        with open(dest_path, "wb") as fh:
            while True:
                chunk = resp.read(_CHUNK)
                if not chunk:
                    break
                fh.write(chunk)
                done += len(chunk)
                if progress_cb is not None:
                    progress_cb(done, total)


# ---------------------------------------------------------------------------
# High-level download functions
# ---------------------------------------------------------------------------

def download_fiji(
    dest_dir: Optional[Path] = None,
    progress_cb: Optional[ProgressCB] = None,
) -> str:
    """Download Fiji for the current platform and return the executable path.

    Parameters
    ----------
    dest_dir:
        Directory in which to extract Fiji. Defaults to
        :func:`get_default_fiji_install_dir`.
    progress_cb:
        Optional ``(bytes_downloaded, total_bytes)`` callback. *total_bytes*
        is -1 when the server omits ``Content-Length``.

    Returns
    -------
    str
        Absolute path to the Fiji binary.

    Raises
    ------
    RuntimeError
        If the Fiji executable cannot be located after extraction.
    """
    if dest_dir is None:
        dest_dir = get_default_fiji_install_dir()
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    url = get_fiji_download_url()
    zip_path = dest_dir / "fiji-download.zip"

    download_with_progress(url, zip_path, progress_cb)

    # Extract zip; the archive contains a top-level "Fiji.app" or "fiji" dir
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)
    zip_path.unlink(missing_ok=True)

    # Locate Fiji.app inside the extracted tree (one level deep)
    fiji_app: Optional[Path] = None
    for candidate in (dest_dir / "Fiji.app", dest_dir / "fiji" / "Fiji.app"):
        if candidate.is_dir():
            fiji_app = candidate
            break
    if fiji_app is None:
        for child in dest_dir.iterdir():
            if child.is_dir():
                nested = child / "Fiji.app"
                if nested.is_dir():
                    fiji_app = nested
                    break

    if fiji_app is None:
        raise RuntimeError(
            f"Fiji.app directory not found after extraction in {dest_dir}. "
            "The downloaded archive may have an unexpected layout."
        )

    exe = fiji_app_to_executable(str(fiji_app))
    if exe is None:
        raise RuntimeError(
            f"Fiji executable not found inside {fiji_app}. "
            "The Fiji installation may be incomplete or incompatible with this platform."
        )

    # Make executable on Unix
    if not is_windows():
        Path(exe).chmod(Path(exe).stat().st_mode | 0o111)

    return exe


def resolve_fiji_plugins_dir(fiji_exe: str) -> Optional[Path]:
    """Return the ``Fiji.app/plugins/`` directory given any path inside a Fiji install.

    Walks upward from *fiji_exe* looking for the ``Fiji.app`` root (identified
    by the presence of a ``plugins/`` child directory), then returns that
    ``plugins/`` path.  Returns *None* if the plugins directory cannot be found.
    """
    p = Path(fiji_exe).expanduser().resolve()
    # Walk ancestors: executable → ImageJ-linux64 → Fiji.app → ...
    for ancestor in (p, *p.parents):
        plugins = ancestor / "plugins"
        if plugins.is_dir():
            return plugins
    return None


def install_thunderstorm_jar(
    fiji_exe: Optional[str] = None,
    src_jar: Optional[Path] = None,
    progress_cb: Optional[ProgressCB] = None,
) -> str:
    """Install ThunderSTORM JAR where Fiji can find it and return its path.

    Strategy (in order):
    1. If *src_jar* is supplied (e.g. the bundled JAR), copy it to the Fiji
       plugins directory derived from *fiji_exe* — or to the default user data
       dir if no Fiji is configured.
    2. If no *src_jar* is supplied, download the JAR from GitHub and place it
       directly in ``Fiji.app/plugins/`` (if *fiji_exe* is known) so that Fiji
       picks it up without any manual copy.

    Parameters
    ----------
    fiji_exe:
        Path to the Fiji executable.  Used to locate ``Fiji.app/plugins/``.
        If *None*, falls back to :func:`get_default_thunderstorm_dir`.
    src_jar:
        Existing JAR to copy instead of downloading.  Typically the bundled
        ``external_plugins/Thunder_STORM.jar``.
    progress_cb:
        ``(bytes_downloaded, total_bytes)`` callback used only when downloading.

    Returns
    -------
    str
        Absolute path to the installed JAR.
    """
    # Determine destination directory
    dest_dir: Path
    if fiji_exe:
        plugins_dir = resolve_fiji_plugins_dir(fiji_exe)
        dest_dir = plugins_dir if plugins_dir is not None else get_default_thunderstorm_dir()
    else:
        dest_dir = get_default_thunderstorm_dir()

    dest_dir.mkdir(parents=True, exist_ok=True)
    jar_dest = dest_dir / "Thunder_STORM.jar"

    if src_jar is not None:
        # Copy the existing JAR (bundled or previously downloaded)
        shutil.copy2(str(src_jar), str(jar_dest))
    else:
        # Download from GitHub
        download_with_progress(get_thunderstorm_download_url(), jar_dest, progress_cb)

    return str(jar_dest)


def download_thunderstorm_jar(
    dest_dir: Optional[Path] = None,
    progress_cb: Optional[ProgressCB] = None,
) -> str:
    """Download the ThunderSTORM JAR to *dest_dir* and return its path.

    Use :func:`install_thunderstorm_jar` instead when a Fiji executable is
    known — it places the JAR directly in ``Fiji.app/plugins/`` so Fiji picks
    it up automatically.

    Parameters
    ----------
    dest_dir:
        Directory to place the JAR. Defaults to
        :func:`get_default_thunderstorm_dir`.
    progress_cb:
        Optional ``(bytes_downloaded, total_bytes)`` callback.

    Returns
    -------
    str
        Absolute path to ``Thunder_STORM.jar``.
    """
    if dest_dir is None:
        dest_dir = get_default_thunderstorm_dir()
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    jar_path = dest_dir / "Thunder_STORM.jar"
    download_with_progress(get_thunderstorm_download_url(), jar_path, progress_cb)
    return str(jar_path)
