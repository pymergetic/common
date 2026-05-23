"""Print or verify PEP 508 specs from ``[tool.pymergetic.pins]`` + ``~=`` lines."""

from __future__ import annotations

import argparse
import subprocess
import sys

from pymergetic.common.devtools.pin_pyproject import pip_install_dry_run_ok
from pymergetic.common.devtools.pins_config import (
    resolve_bump_distributions,
    resolve_wait_distributions,
    single_compatible_pin_spec,
)
from pymergetic.common.devtools.project_paths import resolve_project_root, resolve_pyproject


def main(argv: list[str] | None = None) -> int:
    """CLI: ``pymergetic-pin-specs``."""
    ap = argparse.ArgumentParser(
        description=(
            "Print PEP 508 pin specs from pyproject.toml for [tool.pymergetic.pins] targets.\n"
            "Use --verify-pip to check pip can resolve specs (dry-run; safe on Windows CI)."
        ),
    )
    ap.add_argument("--project-root", type=str, default=None)
    ap.add_argument("--pyproject", type=str, default=None)
    ap.add_argument("--distribution", "-d", default=None)
    ap.add_argument("--wait", action="store_true", help="use pins marked wait = true")
    ap.add_argument("--bump", action="store_true", help="use pins marked bump = true (default)")
    ap.add_argument(
        "--verify-pip",
        action="store_true",
        help="run pip install --dry-run on each spec (does not upgrade pymergetic-common in-place)",
    )
    ap.add_argument(
        "--pip-install",
        action="store_true",
        help="actually pip install specs (local dev only; can fail on Windows if CLIs are in use)",
    )
    ns = ap.parse_args(argv)

    project_root = resolve_project_root(ns.project_root)
    pp = resolve_pyproject(project_root=project_root, pyproject=ns.pyproject)
    if not pp.is_file():
        print(f"error: not a file: {pp}", file=sys.stderr)
        return 2

    text = pp.read_text(encoding="utf-8")
    try:
        if ns.wait:
            dists = resolve_wait_distributions(text, pp.parent, ns.distribution)
        else:
            dists = resolve_bump_distributions(text, pp.parent, ns.distribution)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    specs: list[str] = []
    for dist in dists:
        try:
            specs.append(single_compatible_pin_spec(text, dist))
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2

    if ns.verify_pip:
        for spec in specs:
            if not pip_install_dry_run_ok(spec):
                print(f"error: pip cannot resolve {spec!r}", file=sys.stderr)
                return 1
        print(f"ok: pip can resolve {', '.join(specs)}", flush=True)
        return 0

    if ns.pip_install:
        subprocess.check_call([sys.executable, "-m", "pip", "install", *specs])
        return 0

    print(" ".join(specs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
