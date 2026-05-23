"""Next semver ``v*`` tag and ``git fetch`` / ``tag`` / ``push`` (common repository)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from pymergetic.common.devtools.release_helpers import (
    PYPROJECT_AUTO_COMMIT_MSG,
    dirty_paths,
    ensure_clean_worktree,
    next_v_tag,
    prepare_worktree_for_tag,
    project_name_from_pyproject,
    tag_push_commands,
)


def main(argv: list[str] | None = None, *, repo: Path | None = None) -> int:
    """Entry point for ``pymergetic-release-tag``.

    *repo* defaults to the current working directory (run from the repository root).
    """
    ap = argparse.ArgumentParser(
        description=(
            "Create and push the next pymergetic-common release tag from the latest ``v*`` git tag.\n\n"
            "Default: bump **patch**. Use ``--minor`` / ``--major`` for other segments.\n"
            "If there is no ``v*`` tag yet, starts from **v0.0.0**, then bumps.\n\n"
            "If **only** ``pyproject.toml`` is uncommitted, it is committed and pushed to the "
            "branch before tagging (omit ``--no-auto-commit`` to enable).\n\n"
            "The annotated tag message uses ``[project].name`` from ``pyproject.toml`` plus the version.\n\n"
            "**GitHub vs PyPI:** the tag appears immediately; PyPI upload can still fail."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--patch", action="store_const", dest="level", const="patch", help="bump patch (default)")
    g.add_argument("--minor", action="store_const", dest="level", const="minor", help="bump minor, reset patch")
    g.add_argument("--major", action="store_const", dest="level", const="major", help="bump major")
    ap.set_defaults(level="patch")
    ap.add_argument("--dry-run", action="store_true", help="print commands only; no git writes")
    ap.add_argument("--no-pull", action="store_true", help="skip fetch/checkout/pull")
    ap.add_argument("--no-push", action="store_true", help="tag locally only; do not push")
    ap.add_argument("--remote", default="origin", help="git remote (default: origin)")
    ap.add_argument("--branch", default="main", help="branch to update (default: main)")
    ap.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="git repository root (default: current working directory)",
    )
    ap.add_argument(
        "--no-auto-commit",
        action="store_true",
        help="do not auto-commit / push a sole pyproject.toml change; require a clean tree",
    )
    ns = ap.parse_args(argv)

    root = repo if repo is not None else ns.repo
    if root is None:
        root = Path.cwd()
    root = root.resolve()
    if not (root / ".git").exists() and not (root / ".git").is_file():
        print(f"error: no git state at {root}", file=sys.stderr)
        return 2

    try:
        dist_name = project_name_from_pyproject(root)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    latest, new_tag = next_v_tag(root, level=ns.level)
    msg = f"{dist_name} {new_tag.removeprefix('v')}"
    cmds = tag_push_commands(
        new_tag,
        remote=ns.remote,
        branch=ns.branch,
        no_pull=ns.no_pull,
        no_push=ns.no_push,
        tag_message=msg,
    )

    print(f"latest tag: {latest or '(none)'}")
    print(f"next tag:   {new_tag}  (bump {ns.level})")

    paths = dirty_paths(root)
    auto = not ns.no_auto_commit
    if paths:
        if paths == {"pyproject.toml"} and not auto:
            print(
                "error: pyproject.toml is modified; commit or stash it, "
                "or omit --no-auto-commit to commit and push it automatically before tagging.",
                file=sys.stderr,
            )
            return 1
        if paths != {"pyproject.toml"}:
            print(
                "error: uncommitted changes (not only pyproject.toml); "
                "commit or stash everything, or leave only pyproject.toml dirty for auto-commit.\n"
                + "\n".join(sorted(paths)),
                file=sys.stderr,
            )
            return 1

    if ns.dry_run:
        print("--- dry-run; commands not executed ---")
        if paths == {"pyproject.toml"} and auto:
            print(f"+ git add pyproject.toml && git commit -m {PYPROJECT_AUTO_COMMIT_MSG!r}")
            if not ns.no_push:
                print(f"+ git push {ns.remote} {ns.branch}")
        for c in cmds:
            print("+", " ".join(c))
        return 0

    prepare_worktree_for_tag(
        root,
        auto_commit_pyproject=auto,
        remote=ns.remote,
        branch=ns.branch,
        push_after_commit=not ns.no_push,
    )
    ensure_clean_worktree(root)
    for c in cmds:
        subprocess.run(c, cwd=root, check=True)

    if ns.no_push:
        print(f"done: created {new_tag} locally (not pushed)")
    else:
        print(f"done: pushed {new_tag} (remote={ns.remote}, branch={ns.branch})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
