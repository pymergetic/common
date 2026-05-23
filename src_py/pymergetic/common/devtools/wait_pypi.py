"""Poll PyPI until a ``{distribution}~=…`` pin is published."""

from __future__ import annotations

import argparse
import sys

from pymergetic.common.devtools.pin_pyproject import wait_pypi_for_compatible_pin
from pymergetic.common.devtools.pins_config import resolve_wait_distributions
from pymergetic.common.devtools.project_paths import (
    resolve_project_root,
    resolve_pyproject,
)


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``pymergetic-wait-pypi``."""
    ap = argparse.ArgumentParser(
        description=(
            "Poll PyPI until a release exists for the version pinned as "
            "``{distribution}~=X.Y.Z`` in pyproject.toml.\n\n"
            "Targets come from ``[tool.pymergetic.pins]`` entries with ``wait = true``, "
            "or a sole external ``~=`` pin. Use ``--distribution`` to override."
        ),
    )
    ap.add_argument(
        "--project-root",
        type=str,
        default=None,
        help="package directory containing pyproject.toml (relative or absolute; default: cwd)",
    )
    ap.add_argument(
        "--pyproject",
        type=str,
        default=None,
        help="path to pyproject.toml or its parent directory (overrides --project-root)",
    )
    ap.add_argument(
        "--distribution",
        "-d",
        default=None,
        metavar="NAME",
        help="PyPI distribution to wait for (default: [tool.pymergetic.pins] or infer)",
    )
    ap.add_argument("--timeout", type=int, default=1800, metavar="SEC", help="max wait (default: 1800)")
    ap.add_argument("--interval", type=int, default=30, metavar="SEC", help="seconds between checks (default: 30)")
    ns = ap.parse_args(argv)

    project_root = resolve_project_root(ns.project_root)
    pp = resolve_pyproject(project_root=project_root, pyproject=ns.pyproject)
    if not pp.is_file():
        print(f"error: not a file: {pp}", file=sys.stderr)
        return 2

    text = pp.read_text(encoding="utf-8")
    try:
        dists = resolve_wait_distributions(text, pp.parent, ns.distribution)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    for dist in dists:
        try:
            version, attempts = wait_pypi_for_compatible_pin(
                text,
                dist,
                timeout_s=float(ns.timeout),
                interval_s=float(ns.interval),
                verbose=True,
            )
        except ValueError as e:
            raise SystemExit(str(e)) from None
        except TimeoutError as e:
            print(
                f"error: {e}. "
                "Confirm the dependency’s release workflow finished and PyPI has the artifacts.",
                file=sys.stderr,
            )
            return 1
        print(f"ok: {dist} {version} is on PyPI (attempt {attempts})", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
