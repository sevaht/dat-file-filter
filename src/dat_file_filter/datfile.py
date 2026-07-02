"""Read a dat file, group its entries into games, and write filtered subsets.

Parsing uses ElementTree, which also serves as the writer:
:meth:`DatFile.write` rebuilds the document from the parsed elements and
pretty-prints it, so output is a clean, canonical XML form rather than a copy
of the source's exact bytes.
Writing with no filter (every entry kept) yields a pristine reformatted copy;
diffing that against a filtered write shows only the removed entries (and any
``cloneofid`` stripped because its target was removed). Grouping links variants
by title and by the ``id``/``cloneofid`` clone attributes some dat files
provide.
"""

from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

from .attributes import NO_ENGLISH_SORT_RANK
from .game import Game
from .metadata import Metadata

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .attributes import Disc, Edition, Localization, Tags, Version
    from .metadata import MetadataFilter

_DOCTYPE_RE = re.compile(r"<!DOCTYPE[^>]*>")


def _child_text(element: ET.Element, name: str) -> str:
    child = element.find(name)
    return (child.text or "") if child is not None else ""


def _set_child_text(element: ET.Element, name: str, text: str) -> None:
    child = element.find(name)
    if child is None:
        child = ET.SubElement(element, name)
    child.text = text


def _tree_key(
    metadata: Metadata,
) -> tuple[Edition, Version, Tags, Disc, Localization, str]:
    """Sort key matching the variant tree, so ``min`` gives its first leaf."""
    entity = metadata.entity
    return (
        entity.edition,
        entity.version,
        entity.unhandled_tags,
        entity.disc,
        metadata.localization,
        metadata.title,
    )


def _parent_key(
    metadata: Metadata,
) -> tuple[int, tuple[Edition, Version, Tags, Disc, Localization, str]]:
    """Sort key for choosing a clone group's parent: best English first.

    English rank leads (so any English entry outranks a non-English one); the
    tree key breaks ties, preferring the editionless "main" release.
    """
    priority = metadata.localization.english_priority()
    return (priority or NO_ENGLISH_SORT_RANK, _tree_key(metadata))


class _IdAllocator:
    """Hand out ids not already used, continuing the source's numbering."""

    def __init__(self, used: set[str]) -> None:
        self._used = set(used)
        numeric = [int(value) for value in used if value.isdigit()]
        self._counter = max(numeric, default=0)
        self._width = max((len(v) for v in used if v.isdigit()), default=4)

    def allocate(self) -> str:
        while True:
            self._counter += 1
            candidate = str(self._counter).zfill(self._width)
            if candidate not in self._used:
                self._used.add(candidate)
                return candidate


class _UnionFind:
    """Disjoint-set over strings, for grouping entries into games."""

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def add(self, item: str) -> None:
        self._parent.setdefault(item, item)

    def find(self, item: str) -> str:
        root = item
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[item] != root:  # path compression
            self._parent[item], item = root, self._parent[item]
        return root

    def union(self, first: str, second: str) -> None:
        first_root, second_root = self.find(first), self.find(second)
        if first_root != second_root:
            self._parent[first_root] = second_root


def _fallback_title_union(
    groups: _UnionFind,
    metadata_list: list[Metadata],
    stems_by_title: dict[str, list[str]],
) -> None:
    """Union same-title entries, but never bridge two reliable groups.

    Whatever ``groups`` has merged by now (via clone ids and clone lists) is
    treated as reliable. Same-title entries are then merged as a fallback,
    except when a title is shared by two or more distinct reliable groups:
    those stay apart, and only the loose (non-reliable) same-title entries
    merge.
    """
    root_of = {m.stem: groups.find(m.stem) for m in metadata_list}
    size: dict[str, int] = {}
    for root in root_of.values():
        size[root] = size.get(root, 0) + 1
    reliable = {stem for stem, root in root_of.items() if size[root] > 1}
    for stems in stems_by_title.values():
        reliable_roots = {groups.find(s) for s in stems if s in reliable}
        if len(reliable_roots) <= 1:
            for other in stems[1:]:
                groups.union(stems[0], other)
        else:
            loose = [s for s in stems if s not in reliable]
            for other in loose[1:]:
                groups.union(loose[0], other)


class DatFile:
    def __init__(self, path: Path | str) -> None:
        self.name = ""
        self.entries: dict[str, Metadata] = {}
        self._elements: dict[str, ET.Element] = {}
        self._header: ET.Element | None = None

        raw_bytes = Path(path).read_bytes()
        root = ET.fromstring(raw_bytes)  # noqa: S314
        self._root_tag = root.tag
        self._root_attrib = dict(root.attrib)
        # Preserve a DOCTYPE (ElementTree drops it); it lives near the top.
        doctype = _DOCTYPE_RE.search(
            raw_bytes[:4096].decode("utf-8", "ignore")
        )
        self._doctype = doctype.group(0) if doctype else None

        game_ids: set[str] = set()
        for child in root:
            if child.tag == "header":
                self._header = child
                self.name = _child_text(child, "name")
            elif child.tag == "game":
                self._add_game_element(child, game_ids)

    def _add_game_element(
        self, element: ET.Element, game_ids: set[str]
    ) -> None:
        stem = element.attrib["name"]
        description = _child_text(element, "description")
        if description and stem != description:
            msg = f'description mismatch: "{stem}" != "{description}"'
            raise ValueError(msg)
        if stem in self.entries:
            msg = f"duplicate stem: {stem}"
            raise ValueError(msg)
        game_id = element.attrib.get("id", "")
        clone_of_id = element.attrib.get("cloneofid", "")
        if game_id:
            if game_id in game_ids:
                msg = f"duplicate id: {game_id}"
                raise ValueError(msg)
            game_ids.add(game_id)
        elif clone_of_id:
            msg = f'"{stem}" has no id, but has cloneofid {clone_of_id}'
            raise ValueError(msg)
        self.entries[stem] = Metadata.from_stem(
            stem,
            category=_child_text(element, "category"),
            game_id=game_id,
            clone_of_id=clone_of_id,
        )
        self._elements[stem] = element

    def metadata(
        self, *, metadata_filter: MetadataFilter | None = None
    ) -> Iterator[Metadata]:
        """Yield each entry's metadata, optionally filtered."""
        for metadata in self.entries.values():
            if metadata_filter is None or metadata_filter(metadata):
                yield metadata

    def build_games(
        self,
        *,
        metadata_filter: MetadataFilter | None = None,
        title_groups: list[set[str]] | None = None,
    ) -> dict[str, Game]:
        """Group entries into games keyed by their best English title.

        Clone ids and ``title_groups`` (clone lists) are the reliable,
        verified signals and are applied first. Shared-title matching is only
        a fallback: it keeps a game's variants together when the dat doesn't
        clone-link them all (multi-disc sets, Virtual Console re-releases,
        ...), but it never bridges two entries already in *different* reliable
        groups — so a generic title shared by two distinct games can't merge
        them. Each entry belongs to exactly one game; the result is ordered
        case-insensitively by key.
        """
        metadata_list = list(self.metadata(metadata_filter=metadata_filter))
        by_game_id = {m.game_id: m for m in metadata_list if m.game_id}
        stems_by_title: dict[str, list[str]] = {}
        for metadata in metadata_list:
            stems_by_title.setdefault(metadata.title, []).append(metadata.stem)

        groups = _UnionFind()
        for metadata in metadata_list:
            groups.add(metadata.stem)
        # Reliable grouping first: clone ids, then clone lists.
        for metadata in metadata_list:
            parent = by_game_id.get(metadata.clone_of_id)
            if parent is not None:
                groups.union(metadata.stem, parent.stem)
        for group in title_groups or []:
            stems = [
                s for title in group for s in stems_by_title.get(title, [])
            ]
            for other in stems[1:]:
                groups.union(stems[0], other)
        # Title matching is a fallback and must not bridge reliable groups.
        _fallback_title_union(groups, metadata_list, stems_by_title)

        components: dict[str, list[Metadata]] = {}
        for metadata in metadata_list:
            components.setdefault(groups.find(metadata.stem), []).append(
                metadata
            )

        games: dict[str, Game] = {}
        for members in components.values():
            game = Game(versions=members)
            games[game.english_title or members[0].title] = game
        return dict(sorted(games.items(), key=lambda item: item[0].casefold()))

    def write(
        self, path: Path | str, *, kept: set[str], name: str | None = None
    ) -> int:
        """Write a canonical, pretty-printed copy of the kept entries.

        The output's parent-clone links express how the tool groups games. An
        already-valid clone group whose parent is still present is left
        untouched; links are (re)built only when the parent was removed or the
        entries were grouped by title alone. When (re)building, the best
        English entry becomes the parent and the rest are ``cloneofid`` clones
        of it, so no reference dangles and title-only dats gain clone links.
        ``id`` attributes are assigned only where a link needs one. The header
        ``<name>`` changes only when ``name`` is given. Returns the number of
        entries written.
        """
        kept_ids = {
            element.attrib["id"]
            for stem, element in self._elements.items()
            if stem in kept and element.attrib.get("id")
        }
        allocator = _IdAllocator(kept_ids)
        assign_id: dict[str, str] = {}
        set_clone: dict[str, str | None] = {}
        for game in self.build_games(
            metadata_filter=lambda metadata: metadata.stem in kept
        ).values():
            self._plan_clone_links(
                game.versions, kept_ids, allocator, assign_id, set_clone
            )

        root = ET.Element(self._root_tag, self._root_attrib)
        if self._header is not None:
            header = copy.deepcopy(self._header)
            if name is not None:
                _set_child_text(header, "name", name)
            root.append(header)
        written = 0
        for stem, element in self._elements.items():
            if stem not in kept:
                continue
            game_element = copy.deepcopy(element)
            if stem in assign_id:
                game_element.set("id", assign_id[stem])
            if stem in set_clone:
                clone_of_id = set_clone[stem]
                if clone_of_id is None:
                    game_element.attrib.pop("cloneofid", None)
                else:
                    game_element.set("cloneofid", clone_of_id)
            root.append(game_element)
            written += 1

        ET.indent(root)
        lines = ['<?xml version="1.0"?>']
        if self._doctype:
            lines.append(self._doctype)
        body = ET.tostring(root, encoding="unicode")
        Path(path).write_text(
            "\n".join(lines) + "\n" + body + "\n", encoding="utf-8"
        )
        return written

    def _plan_clone_links(
        self,
        members: list[Metadata],
        kept_ids: set[str],
        allocator: _IdAllocator,
        assign_id: dict[str, str],
        set_clone: dict[str, str | None],
    ) -> None:
        """Assign each kept member's ``id``/``cloneofid`` for the output."""
        if len(members) == 1:
            set_clone[members[0].stem] = None  # nothing to clone; drop any ref
            return

        def clone_of(metadata: Metadata) -> str:
            return self._elements[metadata.stem].attrib.get("cloneofid", "")

        clean_roots = [m for m in members if not clone_of(m)]
        dangling = [
            m for m in members if clone_of(m) and clone_of(m) not in kept_ids
        ]
        if len(clean_roots) == 1 and not dangling:
            return  # already a valid single-parent group; leave it alone

        primary = min(members, key=_parent_key)
        primary_id = self._elements[primary.stem].attrib.get("id")
        if not primary_id:
            primary_id = allocator.allocate()
            assign_id[primary.stem] = primary_id
        set_clone[primary.stem] = None
        for metadata in members:
            if metadata.stem == primary.stem:
                continue
            if not self._elements[metadata.stem].attrib.get("id"):
                assign_id[metadata.stem] = allocator.allocate()
            set_clone[metadata.stem] = primary_id
