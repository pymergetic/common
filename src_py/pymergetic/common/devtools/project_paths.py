"""Resolve package roots and read ``[project]`` metadata from ``pyproject.toml``."""

from __future__ import annotations

import re
from pathlib import Path

from pymergetic.common.devtools.release_helpers import project_name_from_pyproject

_COMPAT_PIN_BASE_RE = re.compile(
    r"([a-zA-Z0-9][a-zA-Z0-9._-]*)(?:\[[^\]]+\])?~=([0-9]+(?:\.[0-9]+)*)"
)


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


def compatible_pin_base_distributions(pyproject_toml: str) -> list[str]:
    """Base PyPI names from every ``NAME`` or ``NAME[extra]`` compatible-release pin."""
    return [m.group(1) for m in _COMPAT_PIN_BASE_RE.finditer(pyproject_toml)]


def resolve_pin_distribution(
    pyproject_toml: str,
    project_root: Path,
    explicit: str | None,
) -> str:
    """Distribution whose ``~=`` pins to read or update.

    Uses *explicit* when set; otherwise the sole pin target that is not ``[project].name``.
    """
    if explicit is not None:
        dist = explicit.strip()
        if not dist:
            raise ValueError("empty --distribution")
        return dist

    project_name = project_name_from_pyproject(project_root)
    bases = compatible_pin_base_distributions(pyproject_toml)
    external = sorted({b for b in bases if b != project_name})
    if len(external) == 1:
        return external[0]
    if not external:
        raise ValueError(
            f"no external `{{name}}~=…` pins in {pyproject_path(project_root)}; "
            "pass --distribution explicitly"
        )
    raise ValueError(
        f"multiple pin targets {external!r} in {pyproject_path(project_root)}; "
        "pass --distribution explicitly"
    )


def resolve_wait_distribution(
    pyproject_toml: str,
    project_root: Path,
    explicit: str | None,
) -> str:
    """PyPI distribution to poll before publish (same rules as :func:`resolve_pin_distribution`)."""
    return resolve_pin_distribution(pyproject_toml, project_root, explicit)
