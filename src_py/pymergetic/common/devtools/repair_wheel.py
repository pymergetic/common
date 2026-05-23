"""cibuildwheel repair helpers (auditwheel / delvewheel) for pymergetic extension packages."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from pymergetic.common.devtools.pins_config import single_compatible_pin_spec
from pymergetic.common.devtools.project_paths import (
    project_name_from_pyproject,
    resolve_project_root,
    resolve_pyproject,
)

MANYLINUX_PLAT = "manylinux_2_28_x86_64"
EASYBIND_DIST = "pymergetic-easybind"


def _easybind_consumer_spec(project_root: Path) -> str:
    pp = resolve_pyproject(project_root=project_root)
    return single_compatible_pin_spec(pp.read_text(encoding="utf-8"), EASYBIND_DIST)


def _easybind_pkg_dir() -> Path:
    import pymergetic.easybind as eb

    return Path(eb.__file__).resolve().parent


def _install(*specs: str) -> None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *specs])


def _easybind_self_dll_add_paths(project_root: Path) -> list[str]:
    build_root = project_root / "build"
    if not build_root.is_dir():
        return []
    seen: set[str] = set()
    paths: list[str] = []
    for dll in build_root.rglob("*.dll"):
        parent = str(dll.parent)
        if parent not in seen:
            seen.add(parent)
            paths.append(parent)
    return sorted(paths)


def repair_linux_consumer(dest_dir: str, wheel: str, project_root: Path) -> None:
    _install(_easybind_consumer_spec(project_root), "auditwheel>=6.4")
    eb_dir = str(_easybind_pkg_dir())
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{eb_dir}:{env.get('LD_LIBRARY_PATH', '')}"
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "auditwheel",
            "-v",
            "repair",
            "--plat",
            MANYLINUX_PLAT,
            "-w",
            dest_dir,
            wheel,
        ],
        env=env,
    )


def repair_linux_self(dest_dir: str, wheel: str) -> None:
    _install("auditwheel>=6.4")
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "auditwheel",
            "-v",
            "repair",
            "--plat",
            MANYLINUX_PLAT,
            "-w",
            dest_dir,
            wheel,
        ],
    )


def repair_windows_consumer(dest_dir: str, wheel: str, project_root: Path) -> None:
    _install(_easybind_consumer_spec(project_root), "delvewheel")
    eb_dir = str(_easybind_pkg_dir())
    subprocess.check_call(
        ["delvewheel", "repair", "--add-path", eb_dir, "-w", dest_dir, wheel],
    )


def repair_windows_self(dest_dir: str, wheel: str, project_root: Path) -> None:
    _install("delvewheel")
    cmd = ["delvewheel", "repair", "-w", dest_dir]
    add_paths = _easybind_self_dll_add_paths(project_root)
    if not add_paths:
        print("warning: no *.dll found under build/; delvewheel may fail", file=sys.stderr)
    for path in add_paths:
        cmd.extend(["--add-path", path])
    cmd.append(wheel)
    subprocess.check_call(cmd)


def repair_wheel(
    dest_dir: str,
    wheel: str,
    *,
    project_root: Path,
    platform: str | None = None,
) -> None:
    plat = platform or sys.platform
    dist = project_name_from_pyproject(project_root)
    is_self = dist == EASYBIND_DIST

    if plat.startswith("linux") or plat == "linux":
        if is_self:
            repair_linux_self(dest_dir, wheel)
        else:
            repair_linux_consumer(dest_dir, wheel, project_root)
    elif plat == "win32" or plat.startswith("win"):
        if is_self:
            repair_windows_self(dest_dir, wheel, project_root)
        else:
            repair_windows_consumer(dest_dir, wheel, project_root)
    else:
        raise SystemExit(f"unsupported platform for wheel repair: {plat!r}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Repair a cibuildwheel output (auditwheel on Linux, delvewheel on Windows). "
            "Consumer packages install the pinned pymergetic-easybind from pyproject.toml; "
            "pymergetic-easybind itself bundles build-tree DLLs on Windows."
        ),
    )
    ap.add_argument("dest_dir", help="output directory for repaired wheel")
    ap.add_argument("wheel", help="input wheel path")
    ap.add_argument("--project-root", type=str, default=None)
    ap.add_argument(
        "--platform",
        choices=("linux", "win32"),
        default=None,
        help="override platform detection (default: sys.platform)",
    )
    ns = ap.parse_args(argv)

    project_root = resolve_project_root(ns.project_root)
    repair_wheel(
        ns.dest_dir,
        ns.wheel,
        project_root=project_root,
        platform=ns.platform,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
