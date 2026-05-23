"""Poll PyPI until a ``{distribution}~=…`` pin is published."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pymergetic.common.devtools.pin_pyproject import wait_pypi_for_compatible_pin


def main(argv: list[str] | None = None, *, default_distribution: str = "pymergetic-common") -> int:
    """Entry point for ``pymergetic-wait-pypi``."""
    ap = argparse.ArgumentParser(
        description=(
            "Poll PyPI until a release exists for the version pinned as "
            "``{distribution}~=X.Y.Z`` in pyproject.toml."
        ),
    )
    ap.add_argument(
        "--pyproject",
        type=Path,
        default=Path("pyproject.toml"),
        help="path to pyproject.toml (default: ./pyproject.toml)",
    )
    ap.add_argument(
        "--distribution",
        default=default_distribution,
        help=f"distribution name in ``{{name}}~=…`` pins (default: {default_distribution})",
    )
    ap.add_argument("--timeout", type=int, default=1800, metavar="SEC", help="max wait (default: 1800)")
    ap.add_argument("--interval", type=int, default=30, metavar="SEC", help="seconds between checks (default: 30)")
    ns = ap.parse_args(argv)

    pp = ns.pyproject.resolve()
    if not pp.is_file():
        print(f"error: not a file: {pp}", file=sys.stderr)
        return 2

    text = pp.read_text(encoding="utf-8")
    try:
        version, attempts = wait_pypi_for_compatible_pin(
            text,
            ns.distribution,
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

    print(f"ok: {ns.distribution} {version} is on PyPI (attempt {attempts})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
