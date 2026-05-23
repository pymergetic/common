"""Bump ``{distribution}~=…`` compatible-release pins in a ``pyproject.toml`` string or file."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pymergetic.common.devtools.pins_config import (
    compatible_pin_specs,
    distribution_waits_on_pypi,
    resolve_bump_distributions,
    single_compatible_pin_spec,
)
from pymergetic.common.devtools.project_paths import (
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
    """Return the newest stable release on PyPI for *package*.

    Uses the ``releases`` map (not only ``info.version``) and fetches twice so CDN/index
    caches do not return a stale latest right after upload.
    """
    from packaging.version import Version

    def _latest(data: dict) -> Version:
        best = _max_stable_pypi_release(data)
        if best is None:
            return Version(str(data["info"]["version"]))
        return best

    fetch_pypi_project_json(package, timeout_s=timeout_s)
    v1 = _latest(fetch_pypi_project_json(package, timeout_s=timeout_s))
    v2 = _latest(fetch_pypi_project_json(package, timeout_s=timeout_s))
    return str(max(v1, v2))


def _max_stable_pypi_release(data: dict):
    """Return the highest stable release ``Version`` with files in PyPI JSON, or ``None``."""
    from packaging.version import InvalidVersion, Version

    releases = data.get("releases") or {}
    best: Version | None = None
    for ver_str, files in releases.items():
        if not files:
            continue
        try:
            ver = Version(ver_str)
        except InvalidVersion:
            continue
        if ver.is_prerelease or ver.is_devrelease:
            continue
        if best is None or ver > best:
            best = ver
    return best


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


def newest_pypi_release_for_compatible_pin(
    distribution: str,
    pin_version: str,
    *,
    timeout_s: float = 30.0,
) -> str | None:
    """Return the newest PyPI release matching ``~={pin_version}``, or None if none yet."""
    from packaging.specifiers import SpecifierSet
    from packaging.version import InvalidVersion, Version

    spec = SpecifierSet(f"~={pin_version}")
    data = fetch_pypi_project_json(distribution, timeout_s=timeout_s)
    releases = data.get("releases") or {}
    best: Version | None = None
    for ver_str, files in releases.items():
        if not files:
            continue
        try:
            ver = Version(ver_str)
        except InvalidVersion:
            continue
        if ver.is_prerelease or ver.is_devrelease:
            continue
        if spec.contains(ver):
            if best is None or ver > best:
                best = ver
    return str(best) if best is not None else None


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


def _pip_install_dry_run_once(requirement: str) -> bool:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--dry-run",
            "--ignore-installed",
            requirement,
        ],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def pip_install_dry_run_ok(requirement: str) -> bool:
    """Return whether ``pip install --dry-run`` can resolve *requirement* right now.

    Runs twice: the first dry-run warms pip's index cache (common right after PyPI upload).
    """
    _pip_install_dry_run_once(requirement)
    return _pip_install_dry_run_once(requirement)


def wait_pypi_for_version(
    distribution: str,
    version: str,
    *,
    timeout_s: float = 1800.0,
    interval_s: float = 30.0,
    verbose: bool = False,
    require_pip: bool = False,
) -> None:
    """Poll until *version* is on PyPI (and optionally until pip can resolve it)."""
    spec = f"{distribution}~={version}"
    if verbose:
        goal = "installable from PyPI" if require_pip else "published on PyPI"
        print(
            f"waiting for {distribution} {version} to be {goal} "
            f"(timeout {timeout_s:.0f}s, interval {interval_s:.0f}s)...",
            flush=True,
        )
    deadline = time.monotonic() + timeout_s
    attempt = 0
    while True:
        attempt += 1
        json_ok = pypi_release_exists(distribution, version)
        pip_ok = json_ok and pip_install_dry_run_ok(spec)
        if json_ok and (pip_ok or not require_pip):
            if verbose and json_ok and require_pip and not pip_ok:
                print("note: PyPI JSON is ready but pip index is still lagging", flush=True)
            return
        if time.monotonic() >= deadline:
            if json_ok and require_pip and not pip_ok:
                state = "JSON only"
            else:
                state = "not on PyPI"
            raise TimeoutError(
                f"timed out waiting for {spec} ({state}"
                + ("; pip must resolve it" if require_pip else "")
                + f") after {timeout_s}s ({attempt} attempts)"
            )
        if verbose:
            remaining = int(max(0, deadline - time.monotonic()))
            if json_ok and require_pip:
                detail = "json ok, pip index lagging"
            else:
                detail = "not on PyPI yet"
            print(
                f"attempt {attempt}: {detail} (retry in {interval_s:.0f}s, ~{remaining}s left)...",
                flush=True,
            )
        time.sleep(interval_s)


def fetch_pypi_version_after_github_tag(
    distribution: str,
    *,
    timeout_s: float = 1800.0,
    interval_s: float = 30.0,
    verbose: bool = False,
) -> str:
    """Return latest PyPI release, waiting if GitHub's newest tag is not published yet."""
    pypi_ver = fetch_pypi_version(distribution)
    try:
        owner_repo = github_owner_repo_from_pypi_distribution(distribution)
        gh_ver = latest_release_version_from_github(owner_repo)
    except ValueError:
        return pypi_ver

    if _semver_tuple(pypi_ver) >= _semver_tuple(gh_ver):
        return pypi_ver

    if verbose:
        print(
            f"note: github.com/{owner_repo} has v{gh_ver} but PyPI latest is {pypi_ver}; "
            "waiting for publish...",
            file=sys.stderr,
            flush=True,
        )
    try:
        wait_pypi_for_version(
            distribution,
            gh_ver,
            timeout_s=timeout_s,
            interval_s=interval_s,
            verbose=verbose,
        )
    except TimeoutError as e:
        raise ValueError(
            f"{e}. Confirm the upstream publish workflow finished, or pass --from-pypi to pin "
            f"the current PyPI latest ({pypi_ver}) without waiting."
        ) from e

    final = fetch_pypi_version(distribution)
    if _semver_tuple(final) >= _semver_tuple(gh_ver):
        return final
    return gh_ver


def wait_pypi_for_compatible_pin(
    pyproject_toml: str,
    distribution: str,
    *,
    timeout_s: float = 1800.0,
    interval_s: float = 30.0,
    verbose: bool = False,
) -> tuple[str, int]:
    """Poll until the pinned ``~={version}`` is on PyPI **and** pip can resolve it."""
    pin_version = single_compatible_pin_version(pyproject_toml, distribution)
    specs = compatible_pin_specs(pyproject_toml, distribution)
    if not specs:
        specs = [f"{distribution}~={pin_version}"]
    if verbose:
        print(
            f"waiting for {', '.join(specs)} to be installable from PyPI "
            f"(timeout {timeout_s:.0f}s, interval {interval_s:.0f}s)...",
            flush=True,
        )
    deadline = time.monotonic() + timeout_s
    attempt = 0
    while True:
        attempt += 1
        json_ok = pypi_release_exists(distribution, pin_version)
        pip_ok = json_ok and all(pip_install_dry_run_ok(spec) for spec in specs)
        if json_ok and pip_ok:
            return pin_version, attempt
        if time.monotonic() >= deadline:
            state = "JSON only" if json_ok and not pip_ok else "not on PyPI"
            raise TimeoutError(
                f"timed out waiting for {distribution}~={pin_version} ({state}; "
                f"pip must resolve {specs!r}) after {timeout_s}s ({attempt} attempts)"
            )
        if verbose:
            remaining = int(max(0, deadline - time.monotonic()))
            detail = "json ok, pip index lagging" if json_ok else "not on PyPI yet"
            print(
                f"attempt {attempt}: {detail} (retry in {interval_s:.0f}s, ~{remaining}s left)...",
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
    v1 = _latest_release_version_from_github_once(owner_repo, token=token, timeout_s=timeout_s)
    v2 = _latest_release_version_from_github_once(owner_repo, token=token, timeout_s=timeout_s)
    return v1 if _semver_tuple(v1) >= _semver_tuple(v2) else v2


def _latest_release_version_from_github_once(
    owner_repo: str,
    *,
    token: str | None = None,
    timeout_s: float = 30.0,
) -> str:
    """Single GitHub tags API scan (see :func:`latest_release_version_from_github`)."""
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
            "Targets come from ``[tool.pymergetic.pins]`` (``bump = true``, default) or a sole "
            "external ``~=`` pin. Use ``--distribution`` to override."
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
        help="PyPI distribution whose ~= pins to bump (default: [tool.pymergetic.pins] or infer)",
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
            "pin to highest vMAJOR.MINOR.PATCH tag on GitHub. "
            "If you pass OWNER/REPO, use that repo instead of discovering it from PyPI metadata. "
            "The tags list can lag a few seconds after you push a new tag; re-run if the pin looks stale. "
            "Set GITHUB_TOKEN for private repos."
        ),
    )
    ap.add_argument(
        "--force-github",
        action="store_true",
        help=(
            "with --from-github / default GitHub pinning: allow bumping to a tag that is not "
            "on PyPI yet (not recommended for [tool.pymergetic.pins] wait = true targets)"
        ),
    )
    ap.add_argument(
        "--no-wait-pypi",
        action="store_true",
        help=(
            "for wait = true pins: pin to the current PyPI latest without waiting for a newer "
            "GitHub tag to finish publishing"
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
        dists = resolve_bump_distributions(text, pyproject.parent, ns.distribution)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    exit_code = 0
    for dist in dists:
        wait_pin = distribution_waits_on_pypi(pyproject.parent, dist)
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
        elif ns.from_github is not None:
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
        elif wait_pin:
            try:
                if ns.no_wait_pypi:
                    ver = fetch_pypi_version(dist)
                else:
                    ver = fetch_pypi_version_after_github_tag(dist, verbose=True)
            except ValueError as e:
                print(f"error: {e}", file=sys.stderr)
                return 1
            ver_source = "pypi"
        else:
            try:
                owner_repo = github_owner_repo_from_pypi_distribution(dist)
                ver = latest_release_version_from_github(owner_repo)
            except ValueError as e:
                print(f"error: {e}", file=sys.stderr)
                return 1
            ver_source = "github"

        if ver_source == "github" and wait_pin and not ns.force_github:
            if not pypi_release_exists(dist, ver):
                print(
                    f"error: {dist}=={ver} is tagged on GitHub but not on PyPI yet.\n"
                    "Wait for the upstream publish workflow, then re-run (default for wait = true "
                    "pins is --from-pypi), or pass --force-github to pin ahead of PyPI.",
                    file=sys.stderr,
                )
                return 1
            specs_probe = [f"{dist}~={ver}"]
            if not pip_install_dry_run_ok(specs_probe[0]):
                print(
                    f"error: {dist}=={ver} is on PyPI JSON but pip cannot resolve {specs_probe[0]!r} yet.\n"
                    "Retry in a minute or use --from-pypi after the index catches up.",
                    file=sys.stderr,
                )
                return 1

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

        if ns.dry_run and ver_source in ("pypi", "installed"):
            try:
                or_ = github_owner_repo_from_pypi_distribution(dist)
                gh_ver = latest_release_version_from_github(or_)
                if _semver_tuple(gh_ver) > _semver_tuple(ver):
                    print(
                        f"hint: github.com/{or_} has v{gh_ver} but {ver_source} gave {ver}. "
                        f"For wait = true pins the default is PyPI; use --from-github to follow tags.",
                    )
            except ValueError:
                pass
        elif ns.dry_run and ver_source == "github" and wait_pin:
            print(
                f"note: {dist} has wait = true; default bump source is PyPI (--from-pypi). "
                "GitHub was used because --from-github was set explicitly.",
                file=sys.stderr,
            )

        text = pyproject.read_text(encoding="utf-8")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
