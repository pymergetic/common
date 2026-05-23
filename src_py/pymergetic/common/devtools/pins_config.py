"""Read ``[tool.pymergetic.pins]`` — declarative auto-bump / wait-for targets."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from pymergetic.common.devtools.release_helpers import project_name_from_pyproject

_COMPAT_PIN_BASE_RE = re.compile(
    r"([a-zA-Z0-9][a-zA-Z0-9._-]*)(?:\[[^\]]+\])?~=([0-9]+(?:\.[0-9]+)*)"
)


def pyproject_path(project_root: Path) -> Path:
    return project_root / "pyproject.toml"


def compatible_pin_base_distributions(pyproject_toml: str) -> list[str]:
    return [m.group(1) for m in _COMPAT_PIN_BASE_RE.finditer(pyproject_toml)]


def load_pyproject_data(project_root: Path) -> dict:
    pp = pyproject_path(project_root)
    if not pp.is_file():
        raise ValueError(f"no pyproject.toml at {pp}")
    data = tomllib.loads(pp.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid pyproject.toml at {pp}")
    return data


def pymergetic_pins_table(data: dict) -> dict[str, dict]:
    """``[tool.pymergetic.pins]`` as ``{distribution: config_table}``."""
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return {}
    pm = tool.get("pymergetic")
    if not isinstance(pm, dict):
        return {}
    pins = pm.get("pins")
    if pins is None:
        return {}
    if not isinstance(pins, dict):
        raise ValueError("[tool.pymergetic.pins] must be a table")
    out: dict[str, dict] = {}
    for name, cfg in pins.items():
        if not isinstance(name, str) or not name.strip():
            continue
        if cfg is None:
            cfg = {}
        if not isinstance(cfg, dict):
            raise ValueError(f"[tool.pymergetic.pins].{name!r} must be a table")
        out[name.strip()] = cfg
    return out


def _pin_flag(cfg: dict, key: str, *, default: bool) -> bool:
    value = cfg.get(key)
    if value is None:
        return default
    return bool(value)


def resolve_bump_distributions(
    pyproject_toml: str,
    project_root: Path,
    explicit: str | None,
) -> list[str]:
    """Distributions to update when running ``pymergetic-pin-pyproject``."""
    if explicit is not None:
        dist = explicit.strip()
        if not dist:
            raise ValueError("empty --distribution")
        return [dist]

    entries = pymergetic_pins_table(load_pyproject_data(project_root))
    bump = sorted(k for k, cfg in entries.items() if _pin_flag(cfg, "bump", default=True))
    if bump:
        return bump

    project_name = project_name_from_pyproject(project_root)
    external = sorted({b for b in compatible_pin_base_distributions(pyproject_toml) if b != project_name})
    if len(external) == 1:
        return external
    if not external:
        raise ValueError(
            f"no [tool.pymergetic.pins] and no external `{{name}}~=…` in {pyproject_path(project_root)}; "
            "add [tool.pymergetic.pins] or pass --distribution"
        )
    raise ValueError(
        f"multiple pin targets {external!r} in {pyproject_path(project_root)}; "
        "use [tool.pymergetic.pins] or pass --distribution"
    )


def resolve_wait_distributions(
    pyproject_toml: str,
    project_root: Path,
    explicit: str | None,
) -> list[str]:
    """Distributions to poll before publish (``pymergetic-wait-pypi``)."""
    if explicit is not None:
        dist = explicit.strip()
        if not dist:
            raise ValueError("empty --distribution")
        return [dist]

    entries = pymergetic_pins_table(load_pyproject_data(project_root))
    wait = sorted(k for k, cfg in entries.items() if _pin_flag(cfg, "wait", default=False))
    if wait:
        return wait

    project_name = project_name_from_pyproject(project_root)
    external = sorted({b for b in compatible_pin_base_distributions(pyproject_toml) if b != project_name})
    if len(external) == 1:
        return external
    if not external:
        raise ValueError(
            f"no [tool.pymergetic.pins] entry with wait = true and no external `{{name}}~=…` "
            f"in {pyproject_path(project_root)}; add e.g. "
            "`[tool.pymergetic.pins]\npymergetic-common = { wait = true }`"
        )
    raise ValueError(
        f"multiple pin targets {external!r}; mark one with wait = true under [tool.pymergetic.pins] "
        "or pass --distribution"
    )


def compatible_pin_specs(pyproject_toml: str, distribution: str) -> list[str]:
    """PEP 508 specs ``name[extra]~=X.Y.Z`` in *pyproject_toml* for base *distribution*."""
    base = re.escape(distribution)
    pat = re.compile(rf"({base}(?:\[[^\]]+\])?~=)([0-9]+(?:\.[0-9]+)*)")
    return [f"{m.group(1)}{m.group(2)}" for m in pat.finditer(pyproject_toml)]


def single_compatible_pin_spec(pyproject_toml: str, distribution: str) -> str:
    """Return the sole matching pin spec or raise ``ValueError``."""
    specs = compatible_pin_specs(pyproject_toml, distribution)
    if not specs:
        raise ValueError(f"no `{distribution}~=…` pin in pyproject.toml")
    vers = {s.split("~=", 1)[1] for s in specs}
    if len(vers) != 1:
        raise ValueError(f"{distribution}~= pins disagree: {sorted(vers)!r}")
    return specs[0]
