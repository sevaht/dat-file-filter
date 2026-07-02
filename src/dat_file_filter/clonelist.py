"""Load Retool clone lists to group cross-named regional releases.

Some dat files (notably Redump disc dats) don't provide clone ids, so games
released under different names per region (``Biohazard`` vs ``Resident Evil``)
can't be grouped by title or clone id alone. Retool's clone lists —
hand-curated per-system groupings, vendored under ``clonelists/`` (BSD-3, see
that folder's LICENSE) — bridge that gap. Each entry keys on the bare title
(``searchTerm``), which matches :attr:`Metadata.title`, so the groupings feed
straight into :meth:`DatFile.build_games`.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    from importlib.resources.abc import Traversable
    from pathlib import Path

_PACKAGE = "dat_file_filter"
_CLONELISTS_DIR = "clonelists"
# Upstream ships an integrity manifest next to the clone lists; it has no
# ``variants`` and is not a system, so it must be skipped when enumerating.
_MANIFEST_FILE = "hash.json"
# Clone-list filenames look like "<system> (No-Intro).json" or
# "<system> (Redump).json".
_SOURCE_SUFFIXES = (" (No-Intro)", " (Redump)")
_MIN_GROUP_SIZE = 2  # a group needs 2+ titles to create a grouping edge


def load_groups(text: str) -> list[set[str]]:
    """Parse a clone-list JSON into groups of titles that are the same game.

    Uses each variant's ``titles`` and ``supersets`` (an enhanced edition is
    the same game); ``compilations`` are skipped, since a multi-game disc is
    not the same game as its constituents. Only groups with two or more titles
    are returned (a single title creates no grouping edge).
    """
    groups: list[set[str]] = []
    for variant in json.loads(text).get("variants", []):
        titles: set[str] = set()
        for key in ("titles", "supersets"):
            for entry in variant.get(key, []):
                search_term = entry.get("searchTerm")
                if search_term:
                    titles.add(search_term)
        if len(titles) >= _MIN_GROUP_SIZE:
            groups.append(titles)
    return groups


def _system_name(filename: str) -> str:
    stem = filename.removesuffix(".json")
    for suffix in _SOURCE_SUFFIXES:
        if stem.endswith(suffix):
            return stem.removesuffix(suffix)
    return stem


def _clonelist_files(directory: Path | None) -> Iterable[Path | Traversable]:
    if directory is not None:
        items: Iterable[Path | Traversable] = sorted(directory.glob("*.json"))
    else:
        root = resources.files(_PACKAGE) / _CLONELISTS_DIR
        items = [i for i in root.iterdir() if i.name.endswith(".json")]
    return [item for item in items if item.name != _MANIFEST_FILE]


def available_systems(directory: Path | None = None) -> list[str]:
    """Sorted, de-duplicated system names of the available clone lists."""
    return sorted(
        {_system_name(item.name) for item in _clonelist_files(directory)}
    )


def find_groups(
    *names: str, directory: Path | None = None
) -> list[set[str]] | None:
    """Return title groups from the clone list matching any of ``names``.

    Each name is a haystack (a dat's header name and/or filename, or an
    explicit ``--system`` value). Picks the clone list whose system name (its
    filename minus the ``(No-Intro)``/``(Redump)`` suffix) is the longest one
    contained in a haystack; if both sources exist for that system, both are
    merged.
    Returns ``None`` when no clone list matches (so the caller can report it),
    or the groups otherwise (possibly empty). ``directory`` reads from an
    external clone-list checkout instead of the bundled snapshot.
    """
    candidates = [
        (len(system), item)
        for item in _clonelist_files(directory)
        if (system := _system_name(item.name))
        and any(system in name for name in names)
    ]
    if not candidates:
        return None
    best = max(length for length, _ in candidates)
    groups: list[set[str]] = []
    for length, item in candidates:
        if length == best:
            groups.extend(load_groups(item.read_text(encoding="utf-8")))
    return groups
