from __future__ import annotations

import sys
from pathlib import Path


def test_header_impl_resolution() -> None:
    # Make the fixture package importable.
    fixtures = Path(__file__).parent / "fixtures"
    sys.path.insert(0, str(fixtures))
    try:
        from hdrpkg import Demo

        inst = Demo()
        assert inst.hello() == "hi"
        assert inst.__class__.__name__ == "DemoImpl"
    finally:
        sys.path.remove(str(fixtures))


