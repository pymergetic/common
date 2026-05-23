"""Next semver ``v*`` tag and ``git fetch`` / ``tag`` / ``push``."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from pymergetic.common.devtools.pin_pyproject import run_pin_pyproject
from pymergetic.common.devtools.project_paths import (
    find_git_root,
    project_distribution,
    resolve_project_root,
    resolve_pyproject,
)
from pymergetic.common.devtools.release_helpers import (
    PYPROJECT_AUTO_COMMIT_MSG,
    dirty_paths,
    ensure_clean_worktree,
    next_v_tag,
    prepare_worktree_for_tag,
    tag_push_commands,
)


def main(argv: list[str] | None = None, *, repo: Path | None = None) -> int:
    """Entry point for ``pymergetic-release-tag``."""
    ap = argparse.ArgumentParser(
        description=(
            "Create and push the next release tag from the latest ``v*`` git tag.\n\n"
            "Default: bump **patch**. Use ``--minor`` / ``--major`` for other segments.\n"
            "If there is no ``v*`` tag yet, starts from **v0.0.0**, then bumps.\n\n"
            "Before tagging, bumps ``~=`` pins from ``[tool.pymergetic.pins]`` (same as "
            "``pymergetic-pin-pyproject``). Use ``--no-pin`` to skip.\n\n"
            "``[project].name`` is read from ``pyproject.toml`` under ``--project-root``.\n"
            "Git operations run in the git root found at or above that directory.\n\n"
            "If **only** ``pyproject.toml`` is uncommitted, it is committed and pushed to the "
            "branch before tagging (omit ``--no-auto-commit`` to enable).\n\n"
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
    root_arg = ap.add_mutually_exclusive_group()
    root_arg.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="package directory containing pyproject.toml (relative or absolute; default: cwd)",
    )
    root_arg.add_argument(
        "--repo",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    ap.add_argument(
        "--no-auto-commit",
        action="store_true",
        help="do not auto-commit / push a sole pyproject.toml change; require a clean tree",
    )
    ap.add_argument(
        "--no-pin",
        action="store_true",
        help="skip pymergetic-pin-pyproject before tagging",
    )
    pin = ap.add_argument_group("pin options (before tag; ignored with --no-pin)")
    pin.add_argument(
        "--distribution",
        "-d",
        default=None,
        metavar="NAME",
        help="PyPI distribution whose ~= pins to bump (default: [tool.pymergetic.pins] or infer)",
    )
    pin.add_argument(
        "--from-pypi",
        action="store_true",
        help="pin from PyPI latest instead of GitHub tags",
    )
    pin.add_argument(
        "--from-github",
        nargs="?",
        const="",
        default=None,
        metavar="OWNER/REPO",
        help="pin from GitHub tags (optional OWNER/REPO override)",
    )
    pin.add_argument(
        "--force-github",
        action="store_true",
        help="allow pinning to a GitHub tag not yet on PyPI",
    )
    pin.add_argument(
        "--no-wait-pypi",
        action="store_true",
        help="for wait = true pins: use current PyPI latest without waiting for a new tag",
    )
    ns = ap.parse_args(argv)

    if repo is not None:
        project_root = repo.resolve()
    else:
        project_root = resolve_project_root(ns.project_root or ns.repo)

    try:
        git_root = find_git_root(project_root)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    try:
        dist_name = project_distribution(project_root)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    pyproject = resolve_pyproject(project_root=project_root)
    try:
        pyproject_rel = pyproject.relative_to(git_root).as_posix()
    except ValueError:
        pyproject_rel = pyproject.name

    if not ns.no_pin:
        print("--- pin pyproject ---")
        pin_rc = run_pin_pyproject(
            project_root,
            distribution=ns.distribution,
            from_pypi=ns.from_pypi,
            from_github=ns.from_github,
            force_github=ns.force_github,
            no_wait_pypi=ns.no_wait_pypi,
            dry_run=ns.dry_run,
            require_targets=False,
        )
        if pin_rc != 0:
            return pin_rc

    latest, new_tag = next_v_tag(git_root, level=ns.level)
    msg = f"{dist_name} {new_tag.removeprefix('v')}"
    cmds = tag_push_commands(
        new_tag,
        remote=ns.remote,
        branch=ns.branch,
        no_pull=ns.no_pull,
        no_push=ns.no_push,
        tag_message=msg,
    )

    print(f"project:    {project_root}")
    print(f"git root:   {git_root}")
    print(f"distribution: {dist_name}")
    print(f"latest tag: {latest or '(none)'}")
    print(f"next tag:   {new_tag}  (bump {ns.level})")

    paths = dirty_paths(git_root)
    auto = not ns.no_auto_commit
    if paths:
        if paths == {pyproject_rel} and not auto:
            print(
                f"error: {pyproject_rel} is modified; commit or stash it, "
                "or omit --no-auto-commit to commit and push it automatically before tagging.",
                file=sys.stderr,
            )
            return 1
        if paths != {pyproject_rel}:
            print(
                "error: uncommitted changes (not only pyproject.toml); "
                f"commit or stash everything, or leave only {pyproject_rel} dirty for auto-commit.\n"
                + "\n".join(sorted(paths)),
                file=sys.stderr,
            )
            return 1

    if ns.dry_run:
        print("--- dry-run; commands not executed ---")
        if paths == {pyproject_rel} and auto:
            print(f"+ git add {pyproject_rel} && git commit -m {PYPROJECT_AUTO_COMMIT_MSG!r}")
            if not ns.no_push:
                print(f"+ git push {ns.remote} {ns.branch}")
        for c in cmds:
            print("+", " ".join(c))
        return 0

    prepare_worktree_for_tag(
        git_root,
        auto_commit_pyproject=auto,
        pyproject_rel=pyproject_rel,
        remote=ns.remote,
        branch=ns.branch,
        push_after_commit=not ns.no_push,
    )
    ensure_clean_worktree(git_root)
    for c in cmds:
        subprocess.run(c, cwd=git_root, check=True)

    if ns.no_push:
        print(f"done: created {new_tag} locally (not pushed)")
    else:
        print(f"done: pushed {new_tag} (remote={ns.remote}, branch={ns.branch})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
