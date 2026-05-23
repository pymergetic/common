"""Resolve package roots and read ``[project]`` metadata from ``pyproject.toml``."""

from __future__ import annotations

from pathlib import Path

from pymergetic.common.devtools.pins_config import compatible_pin_base_distributions
from pymergetic.common.devtools.release_helpers import project_name_from_pyproject


def resolve_project_root(path: Path | str | None = None) -> Path:
    """Return an absolute project directory (relative paths use cwd)."""
    if path is None:
        return Path.cwd().resolve()
    return Path(path).expanduser().resolve()


def pyproject_path(project_root: Path) -> Path:
    """``project_root/pyproject.toml``."""
    return project_root / "pyproject.toml"


def resolve_pyproject(
    *,
    project_root: Path | str | None = None,
    pyproject: Path | str | None = None,
) -> Path:
    """Return ``pyproject.toml`` from *pyproject* (file or directory) or *project_root*."""
    if pyproject is not None:
        p = Path(pyproject).expanduser().resolve()
        if p.is_dir():
            return p / "pyproject.toml"
        return p
    root = resolve_project_root(project_root)
    return pyproject_path(root)


def find_git_root(start: Path) -> Path:
    """Walk up from *start* until a ``.git`` file or directory is found."""
    current = start.resolve()
    for _ in range(32):
        git = current / ".git"
        if git.exists() or git.is_file():
            return current
        if current.parent == current:
            break
        current = current.parent
    raise ValueError(f"no git repository at or above {start}")


def project_distribution(project_root: Path) -> str:
    """``[project].name`` for *project_root*."""
    return project_name_from_pyproject(project_root)


def resolve_pin_distribution(
    pyproject_toml: str,
    project_root: Path,
    explicit: str | None,
) -> str:
    from pymergetic.common.devtools.pins_config import resolve_bump_distributions

    return resolve_bump_distributions(pyproject_toml, project_root, explicit)[0]


def resolve_wait_distribution(
    pyproject_toml: str,
    project_root: Path,
    explicit: str | None,
) -> str:
    from pymergetic.common.devtools.pins_config import resolve_wait_distributions

    return resolve_wait_distributions(pyproject_toml, project_root, explicit)[0]


__all__ = [
    "compatible_pin_base_distributions",
    "find_git_root",
    "project_distribution",
    "pyproject_path",
    "resolve_pin_distribution",
    "resolve_project_root",
    "resolve_pyproject",
    "resolve_wait_distribution",
]
