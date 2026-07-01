"""Group release variants into a collapsible, marked tree.

Metadata is grouped by an ordered list of key functions (edition, then version,
then tags, disc, and localization); each key object renders its own label. The
tree is printed with single-child levels collapsed onto their parent's line, so
only real branch points create indentation. Every entry leaf carries a mark
supplied by the caller (``+``/``~``/``-``) which drives its color.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from .metadata import Metadata

# Ordered grouping keys for a variant hierarchy. Each is sortable (order=True)
# and renders itself via __str__.
_LEVELS: list[Callable[[Metadata], object]] = [
    lambda metadata: metadata.entity.edition,
    lambda metadata: metadata.entity.version,
    lambda metadata: metadata.entity.unhandled_tags,
    lambda metadata: metadata.entity.disc,
    lambda metadata: metadata.localization,
]

# Mark -> rich style. Grouping/header lines carry no mark and no color.
_STYLE_BY_MARK = {"+": "green", "~": "yellow", "-": "red"}


@dataclass
class GroupNode:
    label: str
    children: list[GroupNode] = field(default_factory=list)
    members: list[Metadata] = field(default_factory=list)  # only at leaves
    mark: str | None = None  # set on the per-entry leaves


@dataclass
class MarkedLine:
    text: str
    style: str | None


def _active_levels(
    versions: list[Metadata],
) -> list[Callable[[Metadata], object]]:
    return [
        level for level in _LEVELS if any(bool(level(m)) for m in versions)
    ]


def _group(
    versions: list[Metadata], key_funcs: list[Callable[[Metadata], object]]
) -> list[GroupNode]:
    if not key_funcs:
        return []
    first, rest = key_funcs[0], key_funcs[1:]
    buckets: dict[object, list[Metadata]] = {}
    for metadata in versions:
        buckets.setdefault(first(metadata), []).append(metadata)
    nodes: list[GroupNode] = []
    for key in sorted(buckets):  # type: ignore[type-var]
        members = buckets[key]
        node = GroupNode(label=str(key))
        if rest:
            node.children = _group(members, rest)
        else:
            node.members = members
        nodes.append(node)
    return nodes


def _attach_marks(
    node: GroupNode, game_title: str, mark_for: Callable[[Metadata], str]
) -> None:
    """Replace leaf members with one marked leaf per entry."""
    if node.children:
        for child in node.children:
            _attach_marks(child, game_title, mark_for)
    elif node.members:
        members = sorted(node.members, key=lambda metadata: metadata.title)
        multiple = len(members) > 1
        node.children = [
            GroupNode(
                # Show a title only when it differs from the game (or when
                # siblings need telling apart).
                label=(
                    metadata.title
                    if multiple or metadata.title != game_title
                    else ""
                ),
                mark=mark_for(metadata),
            )
            for metadata in members
        ]
        node.members = []


def build_marked_tree(
    game_title: str,
    versions: list[Metadata],
    mark_for: Callable[[Metadata], str],
) -> GroupNode:
    """Build a variant tree whose entry leaves are marked by ``mark_for``.

    The structure comes from every version, so the full grouping is shown; a
    grouping level is included only when at least one version defines that field
    (so a cartridge-only game shows no ``<Discless>`` placeholder).
    """
    levels = _active_levels(versions)
    root = GroupNode(label=game_title, children=_group(versions, levels))
    if not levels:
        # Every grouped field is empty; keep the versions so titles can expand.
        root.members = versions
    _attach_marks(root, game_title, mark_for)
    return root


@dataclass
class _WorkLine:
    tokens: list[str]
    mark: str | None = None


def render_marked_tree(root: GroupNode) -> list[MarkedLine]:
    """Render a marked tree; each line gets a ``+``/``~``/``-``/space gutter.

    Only lines that terminate at an entry leaf carry a mark (and a color);
    grouping/header lines get a blank gutter.
    """
    lines: list[_WorkLine] = [_WorkLine([root.label])]
    _render_marked(root, level=0, lines=lines)
    return [
        MarkedLine(
            text=f"{line.mark or ' '} {' '.join(line.tokens)}",
            style=_STYLE_BY_MARK.get(line.mark or ""),
        )
        for line in lines
    ]


def _render_marked(
    node: GroupNode, level: int, lines: list[_WorkLine]
) -> None:
    nest = len(node.children) > 1
    for child in node.children:
        if nest:
            child_level = level + 1
            work = _WorkLine([f"{'  ' * child_level}-"], child.mark)
            if child.label:
                work.tokens.append(child.label)
            lines.append(work)
        else:
            child_level = level
            if child.label:
                lines[-1].tokens.append(child.label)
            if child.mark:
                lines[-1].mark = child.mark
        _render_marked(child, child_level, lines)
