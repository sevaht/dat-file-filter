#!/usr/bin/env python3
"""Refresh the bundled Retool clone lists from upstream.

Shallow-clones unexpectedpanda/retool-clonelists-metadata and copies its
``clonelists/*.json`` and ``LICENSE`` into ``src/dat_file_filter/clonelists/``.
Retool is retired; run this to pull in any community updates that still land
upstream (and this is where our own updates would be applied).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

_UPSTREAM = "https://github.com/unexpectedpanda/retool-clonelists-metadata.git"
_DEST = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "dat_file_filter"
    / "clonelists"
)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        clone = ["git", "clone", "--depth", "1", _UPSTREAM, str(repo)]
        subprocess.run(clone, check=True)  # noqa: S603
        source = repo / "clonelists"
        _DEST.mkdir(parents=True, exist_ok=True)
        for stale in _DEST.glob("*.json"):
            stale.unlink()
        count = 0
        for item in sorted(source.glob("*.json")):
            shutil.copy2(item, _DEST / item.name)
            count += 1
        shutil.copy2(repo / "LICENSE", _DEST / "LICENSE")
    print(f"Updated {count} clone lists in {_DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
