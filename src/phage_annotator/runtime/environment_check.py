"""Startup validation for the `project/environment.yml` manifest."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
import re
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENVIRONMENT_FILE = PROJECT_ROOT / "project" / "environment.yml"

_DISTRIBUTION_NAME_ALIASES = {
    "pyqt": "PyQt5",
    "pyqt5": "PyQt5",
    "scikit-learn": "scikit-learn",
    "scikit-image": "scikit-image",
}


@dataclass(frozen=True)
class EnvironmentRequirement:
    """A single dependency requirement extracted from project/environment.yml."""

    name: str
    minimum_version: str | None = None


@dataclass(frozen=True)
class EnvironmentCheckResult:
    """Result of comparing the active runtime with project/environment.yml."""

    manifest_path: Path
    missing_manifest: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        """Return True when the active environment matches startup expectations."""
        return not self.missing_manifest and not self.warnings


def _parse_requirement(raw: str) -> EnvironmentRequirement | None:
    """Parse requirement for the current workflow."""
    text = raw.strip().strip("\"'")
    if not text or text.startswith("#"):
        return None
    if text in {"pip:"} or text.endswith(":"):
        return None
    match = re.match(r"^([A-Za-z0-9_.-]+)\s*(?:>=\s*([A-Za-z0-9_.-]+))?", text)
    if not match:
        return None
    return EnvironmentRequirement(
        name=match.group(1).lower(),
        minimum_version=match.group(2),
    )


def _read_requirements(manifest_path: Path) -> list[EnvironmentRequirement]:
    """Read requirements for the current workflow."""
    requirements: list[EnvironmentRequirement] = []
    in_dependencies = False
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "dependencies:":
            in_dependencies = True
            continue
        if not in_dependencies or not stripped.startswith("- "):
            continue
        requirement = _parse_requirement(stripped[2:])
        if requirement is not None:
            requirements.append(requirement)
    return requirements


def _resolve_manifest_path(manifest_path: Path) -> Path:
    """Resolve the most likely project environment manifest path."""
    if manifest_path.exists():
        return manifest_path
    for cwd_manifest in (
        Path.cwd() / "project" / manifest_path.name,
        Path.cwd() / manifest_path.name,
    ):
        if cwd_manifest.exists():
            return cwd_manifest
    return manifest_path


def _version_tuple(version: str) -> tuple[int, ...]:
    """Handle the version tuple helper flow."""
    parts = re.findall(r"\d+", version)
    return tuple(int(part) for part in parts[:4])


def _version_is_at_least(installed: str, minimum: str) -> bool:
    """Handle the version is at least helper flow."""
    installed_parts = _version_tuple(installed)
    minimum_parts = _version_tuple(minimum)
    width = max(len(installed_parts), len(minimum_parts))
    return installed_parts + (0,) * (width - len(installed_parts)) >= (
        minimum_parts + (0,) * (width - len(minimum_parts))
    )


def _distribution_name(requirement_name: str) -> str:
    """Handle the distribution name helper flow."""
    return _DISTRIBUTION_NAME_ALIASES.get(requirement_name, requirement_name)


def _check_python(requirement: EnvironmentRequirement) -> str | None:
    """Check python for the current workflow."""
    if not requirement.minimum_version:
        return None
    current = ".".join(str(part) for part in sys.version_info[:3])
    if _version_is_at_least(current, requirement.minimum_version):
        return None
    return f"Python {current} is below required {requirement.minimum_version}"


def _check_distribution(requirement: EnvironmentRequirement) -> str | None:
    """Check distribution for the current workflow."""
    distribution = _distribution_name(requirement.name)
    try:
        installed = metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return f"Missing dependency: {distribution}"
    if requirement.minimum_version and not _version_is_at_least(
        installed,
        requirement.minimum_version,
    ):
        return (
            f"{distribution} {installed} is below required "
            f"{requirement.minimum_version}"
        )
    return None


def check_environment(
    manifest_path: Path = DEFAULT_ENVIRONMENT_FILE,
    *,
    emit_warnings: bool = True,
) -> EnvironmentCheckResult:
    """Check the active Python environment against the project manifest."""
    manifest_path = _resolve_manifest_path(manifest_path)
    if not manifest_path.exists():
        warning = f"Environment manifest not found: {manifest_path}"
        if emit_warnings:
            print(f"Environment warning: {warning}", file=sys.stderr)
        return EnvironmentCheckResult(
            manifest_path=manifest_path,
            missing_manifest=True,
            warnings=(warning,),
        )

    warnings: list[str] = []
    for requirement in _read_requirements(manifest_path):
        if requirement.name in {"pip"}:
            continue
        if requirement.name == "python":
            warning = _check_python(requirement)
        else:
            warning = _check_distribution(requirement)
        if warning is not None:
            warnings.append(warning)

    if emit_warnings and warnings:
        print(f"Environment warnings from {manifest_path}:", file=sys.stderr)
        for warning in warnings:
            print(f"- {warning}", file=sys.stderr)

    return EnvironmentCheckResult(
        manifest_path=manifest_path,
        warnings=tuple(warnings),
    )
