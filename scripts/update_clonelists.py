#!/usr/bin/env python3
"""Refresh the bundled Retool clone lists from upstream.

Shallow-clones unexpectedpanda/retool-clonelists-metadata and copies its
``clonelists/*.json`` and ``LICENSE`` into ``src/dat_file_filter/clonelists/``.
Retool is retired; run this to pull in any community updates that still land
upstream.

Because upstream is unmaintained, a couple of curated fixes (open upstream
issues we resolved locally) are re-applied on top of every refresh by
:func:`apply_local_patches`. The copy step above wipes the bundled files, so
without this step the fixes would silently vanish on the next update. Patches
are text-anchored and idempotent: each verifies its anchor matches exactly once
(raising loudly if upstream's layout drifted) and is skipped when already
present, so re-running is safe and format changes fail visibly instead of
corrupting data.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import NamedTuple

_UPSTREAM = "https://github.com/unexpectedpanda/retool-clonelists-metadata.git"
_DEST = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "dat_file_filter"
    / "clonelists"
)

# ---------------------------------------------------------------------------
# Local patches (curated fixes for unmaintained upstream)
# ---------------------------------------------------------------------------
#
# A title within a variant is one line: ``{"searchTerm": "X"}`` (optionally
# with ``, "priority": N``), indented four tabs; files use CRLF endings. Our
# loader only unions ``titles``/``supersets`` searchTerms per variant and
# ignores ``group``/``priority``, but patches stay faithful to Retool's format
# so the vendored snapshot round-trips cleanly and diffs stay readable.

# A (searchTerm, priority) pair; priority ``None`` omits the key.
_Title = tuple[str, "int | None"]


class _Edit(NamedTuple):
    """A single exact-text substitution; ``old`` must occur exactly once."""

    old: str
    new: str


class _Patch(NamedTuple):
    """An ordered set of edits against one file, with a why-string."""

    filename: str
    issue: str
    edits: tuple[_Edit, ...]

    @property
    def sentinel(self) -> str:
        """Text present iff the patch is already applied (last insertion)."""
        return self.edits[-1].new


def _title_line(term: str, priority: int | None, *, comma: bool) -> str:
    tail = "," if comma else ""
    if priority is None:
        body = f'{{"searchTerm": "{term}"}}'
    else:
        body = f'{{"searchTerm": "{term}", "priority": {priority}}}'
    return f"\t\t\t\t{body}{tail}\r\n"


def _variant_open(group: str) -> str:
    """The opening two lines of a variant object (its unique anchor)."""
    return f'\t\t{{\r\n\t\t\t"group": "{group}",'


def _variant_block(group: str, titles: tuple[_Title, ...]) -> str:
    parts = [
        "\t\t{\r\n",
        f'\t\t\t"group": "{group}",\r\n',
        '\t\t\t"titles": [\r\n',
    ]
    last = len(titles) - 1
    parts.extend(
        _title_line(term, priority, comma=index != last)
        for index, (term, priority) in enumerate(titles)
    )
    parts.append("\t\t\t]\r\n")
    parts.append("\t\t},\r\n")
    return "".join(parts)


def _add_group(
    filename: str,
    issue: str,
    *,
    before_group: str,
    group: str,
    titles: tuple[_Title, ...],
) -> _Patch:
    """Insert a new variant immediately before ``before_group``."""
    anchor = _variant_open(before_group)
    return _Patch(
        filename=filename,
        issue=issue,
        edits=(_Edit(old=anchor, new=_variant_block(group, titles) + anchor),),
    )


def _move_last_title(
    filename: str,
    issue: str,
    *,
    term: str,
    priority: int | None,
    after_term: str,
) -> _Patch:
    """Move a title out of its current variant to the end of another.

    ``after_term`` is the (currently last) title of the destination variant;
    the moved entry is appended after it. Both the removal and the append are
    text-anchored so the move survives independent of line numbers.
    """
    return _Patch(
        filename=filename,
        issue=issue,
        edits=(
            _Edit(old=_title_line(term, priority, comma=True), new=""),
            _Edit(
                old=_title_line(after_term, None, comma=False),
                new=(
                    _title_line(after_term, None, comma=True)
                    + _title_line(term, priority, comma=False)
                ),
            ),
        ),
    )


_PCE = "NEC - PC Engine - TurboGrafx-16 (No-Intro).json"
_SNES = "Nintendo - Super Nintendo Entertainment System (No-Intro).json"
_MEGA_DRIVE = "Sega - Mega Drive - Genesis (No-Intro).json"
_PS2 = "Sony - PlayStation 2 (Redump).json"
_EMPIRES = "Shin Sangoku Musou 3 - Empires"
_EMPIRES_PREMIUM = "Shin Sangoku Musou 3 - Empires (Premium Box)"

# Ordering note: the two Mega Drive groups chain — "Jam 2" anchors on the
# "Jam!" group added just before it (they sort adjacent), so "Jam!" is listed
# first. Each patch re-reads the file, so the anchor exists by then.
_LOCAL_PATCHES: tuple[_Patch, ...] = (
    _add_group(
        _PCE,
        "#94 Neutopia <-> Neutopia - Frey no Shou",
        before_group="New Adventure Island",
        group="Neutopia",
        titles=(("Neutopia", None), ("Neutopia - Frey no Shou", None)),
    ),
    _add_group(
        _SNES,
        "#94 Justice Ninja Casey <-> Shounen Ninja Sasuke",
        before_group="Ka-blooey",
        group="Justice Ninja Casey",
        titles=(("Justice Ninja Casey", None), ("Shounen Ninja Sasuke", None)),
    ),
    _add_group(
        _MEGA_DRIVE,
        "#94 Barkley <-> Hoops Shut Up and Jam!",
        before_group="Batman - The Video Game",
        group="Barkley Shut Up and Jam!",
        titles=(
            ("Barkley Shut Up and Jam!", None),
            ("Hoops Shut Up and Jam!", None),
        ),
    ),
    _add_group(
        _MEGA_DRIVE,
        "#94 Barkley <-> Hoops Shut Up and Jam 2",
        before_group="Barkley Shut Up and Jam!",
        group="Barkley Shut Up and Jam 2",
        titles=(
            ("Barkley Shut Up and Jam 2", None),
            ("Hoops Shut Up and Jam 2", None),
        ),
    ),
    _move_last_title(
        _PS2,
        "#95 Premium Box belongs to Dynasty Warriors 4 - Empires",
        term=_EMPIRES_PREMIUM,
        priority=2,
        after_term=_EMPIRES,
    ),
)


def _read_text(path: Path) -> str:
    # newline="" preserves the files' CRLF endings through the round-trip.
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _write_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def apply_local_patches(dest: Path) -> int:
    """Re-apply the curated fixes; return how many were newly applied."""
    applied = 0
    for patch in _LOCAL_PATCHES:
        path = dest / patch.filename
        text = _read_text(path)
        if patch.sentinel in text:
            print(f"  skipped (already present): {patch.issue}")
            continue
        for edit in patch.edits:
            found = text.count(edit.old)
            if found != 1:
                msg = (
                    f"{patch.filename}: anchor for [{patch.issue}] matched "
                    f"{found} times (expected 1). Upstream layout changed — "
                    f"re-derive this patch."
                )
                raise RuntimeError(msg)
            text = text.replace(edit.old, edit.new)
        _write_text(path, text)
        applied += 1
        print(f"  applied: {patch.issue}")
    return applied


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
    applied = apply_local_patches(_DEST)
    print(f"Applied {applied} local patch(es) on top of upstream")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
