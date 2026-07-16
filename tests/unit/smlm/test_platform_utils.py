"""Unit tests for cross-platform Fiji path resolution utilities.

These tests run entirely in-process with no external Fiji installation.
Platform-detection branches are exercised via monkeypatching.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

import phage_annotator.smlm.platform_utils as pu


# ---------------------------------------------------------------------------
# Platform predicates
# ---------------------------------------------------------------------------

class TestPlatformPredicates:
    def test_exactly_one_platform_true(self):
        flags = [pu.is_linux(), pu.is_mac(), pu.is_windows()]
        assert sum(flags) == 1, f"Exactly one platform flag must be True: {flags}"

    def test_predicates_are_bool(self):
        assert isinstance(pu.is_linux(), bool)
        assert isinstance(pu.is_mac(), bool)
        assert isinstance(pu.is_windows(), bool)


# ---------------------------------------------------------------------------
# fiji_app_to_executable — path layout per OS
# ---------------------------------------------------------------------------

class TestFijiAppToExecutable:
    def test_returns_none_for_missing_dir(self, tmp_path):
        missing = tmp_path / "nonexistent_fiji.app"
        assert pu.fiji_app_to_executable(str(missing)) is None

    def test_linux_finds_linux64(self, tmp_path):
        app = tmp_path / "Fiji.app"
        exe = app / "ImageJ-linux64"
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.touch()
        with patch.object(pu, "_SYSTEM", "linux"):
            with patch("platform.machine", return_value="x86_64"):
                result = pu.fiji_app_to_executable(str(app))
        assert result is not None
        assert "ImageJ-linux64" in result

    def test_linux_falls_back_to_linux32(self, tmp_path):
        app = tmp_path / "Fiji.app"
        exe = app / "ImageJ-linux32"
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.touch()
        with patch.object(pu, "_SYSTEM", "linux"):
            with patch("platform.machine", return_value="i686"):
                result = pu.fiji_app_to_executable(str(app))
        assert result is not None
        assert "ImageJ" in result

    def test_mac_finds_macos_executable(self, tmp_path):
        app = tmp_path / "Fiji.app"
        exe = app / "Contents" / "MacOS" / "ImageJ"
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.touch()
        with patch.object(pu, "_SYSTEM", "darwin"):
            result = pu.fiji_app_to_executable(str(app))
        assert result is not None
        assert "MacOS" in result

    def test_windows_finds_fiji_exe(self, tmp_path):
        app = tmp_path / "Fiji.app"
        exe = app / "Fiji.exe"
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.touch()
        with patch.object(pu, "_SYSTEM", "windows"):
            result = pu.fiji_app_to_executable(str(app))
        assert result is not None
        assert "Fiji.exe" in result

    def test_no_executable_returns_none(self, tmp_path):
        app = tmp_path / "Fiji.app"
        app.mkdir()
        with patch.object(pu, "_SYSTEM", "linux"):
            result = pu.fiji_app_to_executable(str(app))
        assert result is None

    def test_expands_tilde(self, tmp_path):
        # Tilde expansion is done via expanduser — just confirm it doesn't crash
        # on a non-existent home-relative path
        result = pu.fiji_app_to_executable("~/ImpossibleFiji_99999999.app")
        assert result is None


# ---------------------------------------------------------------------------
# discover_fiji_executable — env var priority
# ---------------------------------------------------------------------------

class TestDiscoverFijiExecutable:
    def test_env_fiji_executable_direct(self, tmp_path):
        exe = tmp_path / "fiji_fake"
        exe.touch()
        with patch.dict(os.environ, {"FIJI_EXECUTABLE": str(exe)}, clear=False):
            result = pu.discover_fiji_executable()
        assert result == str(exe)

    def test_env_fiji_executable_missing_file_skipped(self, tmp_path):
        missing = tmp_path / "not_here"
        with patch.dict(os.environ, {"FIJI_EXECUTABLE": str(missing), "FIJI_APP": ""}, clear=False):
            with patch.object(pu, "_standard_fiji_app_locations", return_value=[]):
                result = pu.discover_fiji_executable()
        assert result is None

    def test_env_fiji_app_used(self, tmp_path):
        app = tmp_path / "Fiji.app"
        exe = app / "ImageJ-linux64"
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.touch()
        with patch.dict(os.environ, {"FIJI_EXECUTABLE": "", "FIJI_APP": str(app)}, clear=False):
            with patch.object(pu, "_SYSTEM", "linux"):
                with patch("platform.machine", return_value="x86_64"):
                    result = pu.discover_fiji_executable()
        assert result is not None
        assert "ImageJ" in result

    def test_returns_none_when_nothing_found(self, tmp_path):
        with patch.dict(os.environ, {"FIJI_EXECUTABLE": "", "FIJI_APP": ""}, clear=False):
            with patch.object(pu, "_standard_fiji_app_locations", return_value=[]):
                result = pu.discover_fiji_executable()
        assert result is None

    def test_extra_dirs_searched(self, tmp_path):
        app = tmp_path / "CustomFiji.app"
        exe = app / "ImageJ-linux64"
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.touch()
        with patch.dict(os.environ, {"FIJI_EXECUTABLE": "", "FIJI_APP": ""}, clear=False):
            with patch.object(pu, "_standard_fiji_app_locations", return_value=[]):
                with patch.object(pu, "_SYSTEM", "linux"):
                    with patch("platform.machine", return_value="x86_64"):
                        result = pu.discover_fiji_executable(extra_dirs=[str(app)])
        assert result is not None


# ---------------------------------------------------------------------------
# split_command_template — platform-safe splitting
# ---------------------------------------------------------------------------

class TestSplitCommandTemplate:
    def test_simple_posix_split(self):
        parts = pu.split_command_template("/usr/bin/fiji --headless --run=/tmp/macro.ijm")
        assert parts[0] == "/usr/bin/fiji"
        assert "--headless" in parts

    def test_windows_preserves_backslashes(self):
        template = r"C:\Fiji.app\Fiji.exe --headless"
        with patch.object(pu, "_SYSTEM", "windows"):
            parts = pu.split_command_template(template)
        assert any("Fiji.exe" in p or "Fiji.app" in p for p in parts)

    def test_quoted_path_with_spaces(self):
        template = '"/opt/my fiji/ImageJ-linux64" --headless'
        parts = pu.split_command_template(template)
        assert len(parts) >= 2
        assert "ImageJ-linux64" in parts[0]


# ---------------------------------------------------------------------------
# build_fiji_headless_command
# ---------------------------------------------------------------------------

class TestBuildFijiHeadlessCommand:
    def test_returns_list(self):
        cmd = pu.build_fiji_headless_command("/opt/Fiji/ImageJ-linux64", "/tmp/macro.ijm")
        assert isinstance(cmd, list)

    def test_starts_with_executable(self):
        cmd = pu.build_fiji_headless_command("/opt/Fiji/ImageJ-linux64", "/tmp/macro.ijm")
        assert cmd[0] == "/opt/Fiji/ImageJ-linux64"

    def test_contains_headless_flag(self):
        cmd = pu.build_fiji_headless_command("/opt/Fiji/ImageJ-linux64", "/tmp/macro.ijm")
        assert "--headless" in cmd

    def test_macro_path_in_command(self):
        cmd = pu.build_fiji_headless_command("/opt/Fiji/ImageJ-linux64", "/tmp/macro.ijm")
        assert any("macro.ijm" in part for part in cmd)

    def test_extra_args_appended(self):
        cmd = pu.build_fiji_headless_command(
            "/opt/Fiji/ImageJ-linux64",
            "/tmp/macro.ijm",
            extra_args=["--arg1", "--arg2"],
        )
        assert "--arg1" in cmd
        assert "--arg2" in cmd


# ---------------------------------------------------------------------------
# UI placeholders — runtime values (not testing platform branch, just type)
# ---------------------------------------------------------------------------

class TestPlaceholders:
    def test_fiji_executable_placeholder_is_str(self):
        assert isinstance(pu.fiji_executable_placeholder(), str)
        assert len(pu.fiji_executable_placeholder()) > 0

    def test_fiji_app_placeholder_is_str(self):
        assert isinstance(pu.fiji_app_placeholder(), str)
        assert "Fiji" in pu.fiji_app_placeholder()

    def test_thunderstorm_jar_placeholder_is_str(self):
        assert isinstance(pu.thunderstorm_jar_placeholder(), str)
        assert ".jar" in pu.thunderstorm_jar_placeholder()

    def test_all_three_platform_variants(self):
        for system in ("linux", "darwin", "windows"):
            with patch.object(pu, "_SYSTEM", system):
                exe = pu.fiji_executable_placeholder()
                app = pu.fiji_app_placeholder()
                jar = pu.thunderstorm_jar_placeholder()
                assert exe and app and jar


# ---------------------------------------------------------------------------
# pytorch_device_default
# ---------------------------------------------------------------------------

class TestPytorchDeviceDefault:
    def test_returns_string(self):
        result = pu.pytorch_device_default()
        assert isinstance(result, str)
        assert result in ("cuda", "mps", "cpu")

    def test_cpu_when_torch_missing(self):
        with patch.dict("sys.modules", {"torch": None}):
            result = pu.pytorch_device_default()
        assert result == "cpu"
