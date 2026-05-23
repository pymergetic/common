# Releasing pymergetic-common to PyPI

`pymergetic-common` is the **pin factory** for the PymergeticOS stack. Release it **before** packages that depend on `pymergetic-common[easybind]` / `[dev]` from PyPI (easybind, core, cppdantic, …).

## How the version is chosen

- The **PyPI distribution** name is **`pymergetic-common`**. **Import** as **`pymergetic.common`**.
- The **version string** is computed by **setuptools-scm** from **Git** tags:
  - Tag the release commit with **`vMAJOR.MINOR.PATCH`**, e.g. `v0.1.0`.
  - On that tagged commit, the wheel/sdist version is **`0.1.0`** (`no-guess-dev` + `no-local-version`).
  - Untagged trees get dev versions like `0.0.1.post1.devN`. For production PyPI, **build from a clean tree on a release tag**.

## One-off upload (manual)

```bash
python -m pip install build twine
git fetch --tags
python -m build
twine check dist/*
twine upload dist/*
```

## Helper: next semver tag + push

**`pymergetic-release-tag`** (after `pip install -e .` or `uv sync` in os-sdk) bumps the latest **`v*`** tag (patch by default), optionally commits a sole dirty **`pyproject.toml`**, and pushes branch + tag.

```bash
# from the package repo, or pass --project-root (relative or absolute)
pymergetic-release-tag --dry-run
pymergetic-release-tag

# from os-sdk (or any parent directory)
pymergetic-release-tag --project-root packages/common --dry-run
pymergetic-release-tag --project-root packages/easybind --minor
```

``[project].name`` is read from ``pyproject.toml`` under ``--project-root``. Git commands run in the git root at or above that directory.

Without install:

```bash
PYTHONPATH=src_py python -m pymergetic.common.devtools.release_tag --dry-run
```

**Tag ≠ PyPI success:** the tag appears on GitHub immediately; the **Publish** workflow can still fail. Fix the branch and push a **new** `v*` tag to ship a new version (PyPI does not replace released files).

## CI upload

Pushing a tag matching `v*` triggers `.github/workflows/publish.yml` (sdist + pure-Python wheel). Set **`PYPI_API_TOKEN`** on the **common** repository (or use [trusted publishing](https://docs.pypi.org/trusted-publishers/)).

Re-runs for the same tag use **`skip-existing: true`** so duplicate uploads do not fail the job.

## Devtools (release / pin bumps)

**Canonical implementation:** `pymergetic.common.devtools` in **pymergetic-common**. Install **`pymergetic-common`** (or **`pymergetic-easybind`**, which depends on it).

**CLIs** — pass **`--project-root PATH`** when not in the package directory (relative or absolute). Install **`pymergetic-common[release]`** from PyPI for standalone use (no monorepo required).

| CLI | `--distribution` |
|-----|------------------|
| `pymergetic-release-tag` | not used — reads `[project].name` |
| `pymergetic-pin-pyproject` | optional — uses `[tool.pymergetic.pins]` or infers |
| `pymergetic-wait-pypi` | optional — uses `[tool.pymergetic.pins]` `wait = true` |
| `pymergetic-pin-specs` | optional — prints/installs pin specs for CI hooks |

Declare targets once in **`pyproject.toml`**:

```toml
[tool.pymergetic.pins]
pymergetic-common = { wait = true }   # consumer: wait before publish; bump on pin
nanobind = {}                         # pin factory: bump all listed keys
pymergetic-easybind = {}
```

Keep **one** ``distribution[extra]~=X.Y.Z`` line per pinned upstream (usually **`[build-system] requires`**). Devtools update that line; they do not duplicate the version elsewhere.

**Pin source:** entries with ``wait = true`` (publish blockers) default to **PyPI** when bumping — not the GitHub tag — so you do not pin ``0.0.4`` before pip can install it. The **pin factory** (common) still defaults to **GitHub tags** for ``nanobind`` / ``pymergetic-easybind``.

```bash
pymergetic-pin-pyproject --project-root packages/easybind
pymergetic-pin-pyproject --project-root packages/common
pymergetic-wait-pypi --project-root packages/easybind
pymergetic-release-tag --project-root packages/common --dry-run
```

**Python API:**

```python
from pymergetic.common.devtools import (
    bump_compatible_pins_in_file,
    fetch_pypi_version,
    latest_release_version_from_github,
    github_owner_repo_from_pypi_distribution,
)
```

## Release order (typical)

1. **common** — tag `vA.B.C`, wait for PyPI.
2. **easybind** — bump `pymergetic-common` / `nanobind` pins in common if needed; release easybind; consumers bump `pymergetic-easybind~=…`.
3. **Hybrid packages** (cppdantic, synapse, …) — bump pins, tag, publish.

## Submodule / os-sdk note

If this repo is a **git submodule** under os-sdk, **tags must exist on the common repository remote**, not only on the parent repo. Tag and release from **`packages/common`** (or push tags to `github.com/pymergetic/common`).

In os-sdk, use **`uv sync`** at the repo root for editable workspace installs; PyPI releases still come from each package’s own repo + `v*` tags.
