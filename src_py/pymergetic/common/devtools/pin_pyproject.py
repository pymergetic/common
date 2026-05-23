"""Bump ``{distribution}~=…`` compatible-release pins in a ``pyproject.toml`` string or file."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pymergetic.common.devtools.project_paths import (
    resolve_pin_distribution,
    resolve_project_root,
    resolve_pyproject,
)

# PEP 440 version suitable for ``~=`` RHS in typical pyproject pins (numeric release).
_VERSION_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)*$")

# Release tags: ``vMAJOR.MINOR.PATCH`` (GitHub / git tag style).
_V_SEMVER_TAG = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def _semver_tuple(version: str) -> tuple[int, ...]:
    """Numeric tuple for comparing ``X.Y.Z`` style pins."""
    return tuple(int(p) for p in version.split("."))

# Reject pathological / mistaken distribution strings (full re.escape covers the rest).
_DIST_OK = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")

# ``https://github.com/OWNER/REPO`` (and ``…/tree/…``, ``.git``, …).
_GITHUB_OWNER_REPO = re.compile(
    r"https?://github\.com/([^/]+)/([^/#?]+)",
    re.IGNORECASE,
)


def _pin_pattern(distribution: str) -> re.Pattern[str]:
    if not _DIST_OK.match(distribution):
        raise ValueError(
            f"invalid distribution name for pin replacement: {distribution!r} "
            "(expected a PyPI-style name, e.g. pymergetic-easybind, cppdantic, scikit-build-core)"
        )
    base = re.escape(distribution)
    return re.compile(rf"({base}(?:\[[^\]]+\])?~=)([0-9]+(?:\.[0-9]+)*)")


def fetch_pypi_project_json(distribution: str, *, timeout_s: float = 30.0) -> dict:
    """Return the JSON object from ``https://pypi.org/pypi/{distribution}/json``."""
    url = f"https://pypi.org/pypi/{distribution}/json"
    try:
        with urlopen(url, timeout=timeout_s) as r:
            return json.load(r)
    except HTTPError as e:
        if e.code == 404:
            raise ValueError(f"no PyPI project named {distribution!r}") from e
        raise


def fetch_pypi_version(package: str = "pymergetic-common", *, timeout_s: float = 30.0) -> str:
    """Return ``info.version`` from ``https://pypi.org/pypi/{package}/json``."""
    data = fetch_pypi_project_json(package, timeout_s=timeout_s)
    return str(data["info"]["version"])


def github_owner_repo_from_pypi_distribution(distribution: str, *, timeout_s: float = 30.0) -> str:
    """Return ``OWNER/REPO`` by scanning PyPI ``home_page`` and ``project_urls`` for ``github.com``.

    Works for any PyPI name whose metadata includes a ``github.com/OWNER/REPO`` link.
    If nothing matches, raises ``ValueError`` — then pass ``--from-github OWNER/REPO`` explicitly.
    """
    data = fetch_pypi_project_json(distribution, timeout_s=timeout_s)
    info = data.get("info") or {}
    urls: list[str] = []
    pu = info.get("project_urls")
    if isinstance(pu, dict):
        for key in ("Source", "Repository", "Homepage", "Code"):
            v = pu.get(key)
            if isinstance(v, str) and v.strip():
                urls.append(v.strip())
        for v in pu.values():
            if isinstance(v, str) and v.strip() and v.strip() not in urls:
                urls.append(v.strip())
    hp = info.get("home_page")
    if isinstance(hp, str) and hp.strip():
        urls.append(hp.strip())

    for u in urls:
        m = _GITHUB_OWNER_REPO.search(u)
        if m:
            repo = m.group(2).removesuffix(".git")
            return f"{m.group(1)}/{repo}"

    raise ValueError(
        f"no github.com URL in PyPI metadata for {distribution!r}; "
        "set project URLs on PyPI or pass --from-github OWNER/REPO"
    )


def pypi_release_exists(package: str, version: str, *, timeout_s: float = 15.0) -> bool:
    """Return True if ``https://pypi.org/pypi/{package}/{version}/json`` exists (release uploaded)."""
    url = f"https://pypi.org/pypi/{package}/{version}/json"
    try:
        with urlopen(url, timeout=timeout_s) as r:
            return getattr(r, "status", 200) == 200
    except HTTPError as e:
        if e.code == 404:
            return False
        raise


def compatible_pin_versions(pyproject_toml: str, distribution: str) -> list[str]:
    """Return every version string from ``{distribution}~=VERSION`` pins (order preserved)."""
    pat = _pin_pattern(distribution)
    return [m.group(2) for m in pat.finditer(pyproject_toml)]


def single_compatible_pin_version(
    pyproject_toml: str,
    distribution: str,
    *,
    empty_pins_suffix: str = "",
) -> str:
    """Return the version string if all ``{distribution}~=…`` pins agree; else raise ``ValueError``."""
    vers = compatible_pin_versions(pyproject_toml, distribution)
    if not vers:
        raise ValueError(
            f"no `{distribution}~=...` pins in pyproject.toml{empty_pins_suffix}"
        )
    uniq = set(vers)
    if len(uniq) != 1:
        raise ValueError(
            f"{distribution}~= pins disagree: {sorted(uniq)!r}; fix pyproject.toml first"
        )
    return vers[0]


def wait_pypi_for_compatible_pin(
    pyproject_toml: str,
    distribution: str,
    *,
    timeout_s: float = 1800.0,
    interval_s: float = 30.0,
    verbose: bool = False,
) -> tuple[str, int]:
    """Poll PyPI until ``pypi_release_exists(distribution, version)`` for the pin.

    Uses ``single_compatible_pin_version`` on *pyproject_toml*. Returns
    ``(resolved_version, attempt_count)``. Raises ``TimeoutError`` if the release
    never appears within *timeout_s*. With *verbose*, log progress to stdout.
    """
    version = single_compatible_pin_version(pyproject_toml, distribution)
    if verbose:
        print(
            f"waiting for {distribution}=={version} on PyPI "
            f"(timeout {timeout_s:.0f}s, interval {interval_s:.0f}s)...",
            flush=True,
        )
    deadline = time.monotonic() + timeout_s
    attempt = 0
    while True:
        attempt += 1
        if pypi_release_exists(distribution, version):
            return version, attempt
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"timed out waiting for {distribution}=={version} on PyPI "
                f"after {timeout_s}s ({attempt} attempts)"
            )
        if verbose:
            remaining = int(max(0, deadline - time.monotonic()))
            print(
                f"attempt {attempt}: not yet (retry in {interval_s:.0f}s, ~{remaining}s left)...",
                flush=True,
            )
        time.sleep(interval_s)


def installed_distribution_version(package: str = "pymergetic-common") -> str:
    """Return ``importlib.metadata.version(package)`` for the active environment."""
    from importlib.metadata import version

    return version(package)


def compatible_release_pin_from_installed_version(pep440: str) -> str:
    """Map an installed PEP 440 version (e.g. setuptools-scm ``0.2.7.post1.dev0``) to ``MAJOR.MINOR.PATCH`` for ``~=`` pins."""
    from packaging.version import Version

    v = Version(pep440)
    rel = list(v.release)
    if not rel:
        raise ValueError(f"no release segment in {pep440!r}")
    while len(rel) < 3:
        rel.append(0)
    return f"{rel[0]}.{rel[1]}.{rel[2]}"


def _github_request_json(url: str, *, token: str | None, timeout_s: float) -> object:
    req = Request(url, headers={"Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urlopen(req, timeout=timeout_s) as r:
        return json.load(r)


def latest_release_version_from_github(
    owner_repo: str,
    *,
    token: str | None = None,
    timeout_s: float = 30.0,
) -> str:
    """Return the highest ``vMAJOR.MINOR.PATCH`` tag on GitHub as ``X.Y.Z`` (no local git clone).

    Uses ``GET /repos/{owner}/{repo}/tags`` (paginated). Works when the tag exists on GitHub but
    PyPI has not published the wheel yet. *owner_repo* is ``OWNER/REPO``.

    The tags endpoint can lag a few seconds right after you push a new tag (eventual consistency /
    caching). If the version looks stale, wait and call again.

    Set ``GITHUB_TOKEN`` or ``GH_TOKEN`` (or pass *token*) for private repos or higher rate limits.
    """
    s = owner_repo.strip().strip("/")
    parts = s.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"expected OWNER/REPO, got {owner_repo!r}")

    owner, repo = parts[0], parts[1]
    tok = token if token is not None else os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    best: tuple[int, int, int] | None = None
    best_ver: str | None = None
    page = 1
    per_page = 100
    while page <= 100:
        url = f"https://api.github.com/repos/{owner}/{repo}/tags?per_page={per_page}&page={page}"
        try:
            data = _github_request_json(url, token=tok, timeout_s=timeout_s)
        except HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            raise ValueError(
                f"GitHub API HTTP {e.code} for {owner}/{repo} (set GITHUB_TOKEN for private repos): {detail}"
            ) from e
        if not isinstance(data, list) or len(data) == 0:
            break
        for item in data:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str):
                continue
            m = _V_SEMVER_TAG.fullmatch(name.strip())
            if not m:
                continue
            t = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if best is None or t > best:
                best = t
                best_ver = f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
        if len(data) < per_page:
            break
        page += 1

    if best_ver is None:
        raise ValueError(f"no vMAJOR.MINOR.PATCH tags found for github.com/{owner}/{repo}")
    return best_ver


def bump_compatible_pins(pyproject_toml: str, distribution: str, version: str) -> tuple[str, int]:
    """Replace each ``{distribution}~=X.Y.Z`` with ``{distribution}~={version}``.

    Returns ``(new_text, replacement_count)``.
    """
    if not _VERSION_RE.match(version):
        raise ValueError(f"invalid PEP 440 version for pin: {version!r}")

    pat = _pin_pattern(distribution)

    def repl(m: re.Match[str]) -> str:
        return f"{m.group(1)}{version}"

    new_text, n = pat.subn(repl, pyproject_toml)
    return new_text, n


def bump_compatible_pins_in_file(
    pyproject: Path | str,
    distribution: str,
    version: str,
    *,
    dry_run: bool = False,
) -> int:
    """Read ``pyproject.toml``, apply :func:`bump_compatible_pins`, write back unless ``dry_run``.

    Returns the number of replacements. Raises ``ValueError`` if no matching pin exists.
    """
    path = Path(pyproject)
    text = path.read_text(encoding="utf-8")
    new_text, n = bump_compatible_pins(text, distribution, version)
    if n == 0:
        raise ValueError(f"no `{distribution}~=...` pin found in {path}")
    if new_text == text:
        return n
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return n


def bump_common_compatible_pins(pyproject_toml: str, version: str) -> tuple[str, int]:
    """Same as :func:`bump_compatible_pins` with ``distribution=\"pymergetic-common\"``."""
    return bump_compatible_pins(pyproject_toml, "pymergetic-common", version)


def bump_common_compatible_pins_in_file(
    pyproject: Path | str,
    version: str,
    *,
    dry_run: bool = False,
) -> int:
    """Same as :func:`bump_compatible_pins_in_file` with ``distribution=\"pymergetic-common\"``."""
    return bump_compatible_pins_in_file(pyproject, "pymergetic-common", version, dry_run=dry_run)


def bump_easybind_compatible_pins(pyproject_toml: str, version: str) -> tuple[str, int]:
    """Same as :func:`bump_compatible_pins` with ``distribution=\"pymergetic-easybind\"``."""
    return bump_compatible_pins(pyproject_toml, "pymergetic-easybind", version)


def bump_easybind_compatible_pins_in_file(
    pyproject: Path | str,
    version: str,
    *,
    dry_run: bool = False,
) -> int:
    """Same as :func:`bump_compatible_pins_in_file` with ``distribution=\"pymergetic-easybind\"``."""
    return bump_compatible_pins_in_file(pyproject, "pymergetic-easybind", version, dry_run=dry_run)


def main(argv: list[str] | None = None) -> int:
    """CLI: ``pymergetic-pin-pyproject`` (see ``--help``)."""
    ap = argparse.ArgumentParser(
        description=(
            "Set every {distribution}~= pin in pyproject.toml. "
            "Default version is the highest vX.Y.Z tag on GitHub for that distribution's repo "
            "(github.com/OWNER/REPO is read from PyPI project URLs; override with --from-github ORG/REPO). "
            "The GitHub tags API can lag briefly after a new tag push. "
            "Use --from-pypi for PyPI's published latest instead. "
            "--version / --installed are explicit overrides.\n\n"
            "``--distribution`` is optional when the project has exactly one external "
            "compatible-release pin (not ``[project].name``)."
        )
    )
    ap.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="package directory containing pyproject.toml (relative or absolute; default: cwd)",
    )
    ap.add_argument(
        "--distribution",
        "-d",
        default=None,
        metavar="NAME",
        help="PyPI distribution whose ~= pins to bump (default: infer from pyproject.toml)",
    )
    ap.add_argument(
        "--pyproject",
        type=Path,
        default=None,
        help="path to pyproject.toml or its parent directory (overrides --project-root)",
    )
    ap.add_argument(
        "--version",
        metavar="X.Y.Z",
        default=None,
        help="pin to this exact release (e.g. CI still publishing or tags API stale)",
    )
    ap.add_argument(
        "--installed",
        action="store_true",
        help="use installed version for --distribution, normalized to X.Y.Z (dev/post/local stripped)",
    )
    ap.add_argument(
        "--from-pypi",
        action="store_true",
        help=(
            "use latest published version from PyPI (pypi.org/.../json info.version) instead of "
            "the default (latest GitHub v* tag)"
        ),
    )
    ap.add_argument(
        "--from-github",
        nargs="?",
        const="",
        default=None,
        metavar="OWNER/REPO",
        help=(
            "same default as no flag: pin to highest vMAJOR.MINOR.PATCH tag on GitHub. "
            "If you pass OWNER/REPO, use that repo instead of discovering it from PyPI metadata. "
            "The tags list can lag a few seconds after you push a new tag; re-run if the pin looks stale. "
            "Set GITHUB_TOKEN for private repos."
        ),
    )
    ap.add_argument("--dry-run", action="store_true", help="do not write the file")
    ns = ap.parse_args(argv)

    nsrc = sum(
        1
        for x in (
            ns.version is not None,
            ns.installed,
            ns.from_pypi,
            ns.from_github is not None,
        )
        if x
    )
    if nsrc > 1:
        print(
            "error: use at most one of --version, --installed, --from-pypi, or --from-github",
            file=sys.stderr,
        )
        return 2

    pyproject = resolve_pyproject(project_root=resolve_project_root(ns.project_root), pyproject=ns.pyproject)
    if not pyproject.is_file():
        print(f"error: {pyproject} not found", file=sys.stderr)
        return 2

    text = pyproject.read_text(encoding="utf-8")
    try:
        dist = resolve_pin_distribution(text, pyproject.parent, ns.distribution)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    ver_source: str
    if ns.installed:
        raw_installed = installed_distribution_version(dist)
        try:
            ver = compatible_release_pin_from_installed_version(raw_installed)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        if raw_installed != ver:
            print(
                f"note: installed {dist}=={raw_installed!r} -> pin ~={ver} (PEP 440 release triple)",
                file=sys.stderr,
            )
        ver_source = "installed"
    elif ns.from_pypi:
        try:
            ver = fetch_pypi_version(dist)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        ver_source = "pypi"
    elif ns.version is not None:
        ver = ns.version.strip()
        ver_source = "explicit"
    else:
        # Default and --from-github [OWNER/REPO]: latest v* tag on GitHub.
        raw = ns.from_github.strip() if ns.from_github is not None else ""
        try:
            if not raw:
                owner_repo = github_owner_repo_from_pypi_distribution(dist)
            else:
                owner_repo = raw
            ver = latest_release_version_from_github(owner_repo)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        ver_source = "github"

    if not _VERSION_RE.match(ver):
        print(f"error: bad version string: {ver!r}", file=sys.stderr)
        return 2

    try:
        n = bump_compatible_pins_in_file(pyproject, dist, ver, dry_run=ns.dry_run)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    action = "would update" if ns.dry_run else "updated"
    print(f"{action} {n} {dist}~= pin(s) to ~={ver} in {pyproject}")

    # PyPI / venv often lag a v* tag on GitHub (default pin source is GitHub).
    if ns.dry_run and ver_source in ("pypi", "installed"):
        try:
            or_ = github_owner_repo_from_pypi_distribution(dist)
            gh_ver = latest_release_version_from_github(or_)
            if _semver_tuple(gh_ver) > _semver_tuple(ver):
                print(
                    f"hint: github.com/{or_} has v{gh_ver} but {ver_source} gave {ver}. "
                    f"Default pinning follows GitHub tags; run: pymergetic-pin-pyproject --project-root {pyproject.parent} --dry-run",
                )
        except ValueError:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
