# pymergetic-common

`pymergetic-common` is the PymergeticOS **foundation package**.

It centralizes:

- **Python dependency groups** (extras) used across Pymergetic packages
- Shared low-level Python utilities (e.g., header/impl wiring)

C++ extension builds use **`pymergetic-easybind`** via the `easybind` extra below.

## Dependency groups (extras)

Install with `pip install pymergetic-common[GROUP]` or `uv pip install -e "packages/common[GROUP]"`.

| Extra | Purpose |
|-------|---------|
| `config` | pydantic, pydantic-settings, pyyaml (included in base install) |
| `console` | fire, rich, textual |
| `objects` | pyzmq |
| `pki` | cryptography |
| `builder` | pyinstaller |
| `nanobind` | **`nanobind~=…` pin** |
| `bind` | nanobind + scikit-build stack (no `pymergetic-easybind` — for building easybind itself) |
| `easybind` | **`bind` + `pymergetic-easybind~=…`** — C++ extension consumer stack |
| `test` | pytest, pytest-asyncio |
| `release` | build, twine |
| `all` | all of the above |
| `dev` | alias for `all` |

Other packages should **re-export** these groups instead of duplicating pins, e.g.:

```toml
[project.optional-dependencies]
dev = ["pymergetic-common[dev]"]
```

C++ extension packages (cppdantic, synapse, axon): use `pymergetic-common[easybind]`.

## os-sdk workspace install

From the os-sdk repo root:

```bash
uv sync
```

Or:

```bash
./scripts/dev-install.sh
```

Standalone package install:

```bash
uv pip install -e "packages/common[dev]"
```

## Releasing

Versioning, tagging, and PyPI CI mirror **pymergetic-easybind**. See **[RELEASING.md](RELEASING.md)**.

```bash
pymergetic-release-tag --project-root packages/common --dry-run
pymergetic-release-tag --project-root packages/common
```

Dev CLIs (install **`pymergetic-common[release]`** from PyPI, or `uv sync` in os-sdk). Use **`--project-root`** when not cd'd into the package repo:

- **`pymergetic-release-tag`** — next `v*` tag + push
- **`pymergetic-pin-pyproject`** — bump `{distribution}~=…` pins
- **`pymergetic-wait-pypi`** — poll until a pinned release is on PyPI

Implementation: **`pymergetic.common.devtools`**. See **[RELEASING.md](RELEASING.md)**.
