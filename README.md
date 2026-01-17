# pymergetic-common

`pymergetic-common` is the PymergeticOS **foundation package**.

It centralizes:

- **Python dependency groups** (extras) used across Pymergetic packages
- **C++ build-time SDK** helpers (CMake interface target + macros) to unify hybrid extension builds
- Shared low-level Python utilities (e.g., header/impl wiring)

## Samples (runnable)

Prereq (repo root):

```bash
cd /home/rr/pymergetic/os-sdk
uv pip install -e "packages/common[dev]"
```

Run `PyObject` (runtime handle) sample:

```bash
/home/rr/pymergetic/os-sdk/.venv/bin/python packages/common/examples/pyobject_pydantic.py
```

Run `PyDataObject` (pure data, idempotent bytes roundtrip) sample:

```bash
/home/rr/pymergetic/os-sdk/.venv/bin/python packages/common/examples/pydataobject_roundtrip.py
```


