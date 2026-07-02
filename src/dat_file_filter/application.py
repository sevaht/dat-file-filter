"""Command-line entry point.

One command: selection flags decide which entries are *kept*; output flags
decide what to emit (a grouped tree, a flat list, a written dat, or surveys of
the data). Trees and lists mark each entry ``+`` (kept, English), ``~`` (kept,
no English), or ``-`` (removed).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from sevaht_utility.log_utility import add_log_arguments, configure_logging

from .console import configure_color, print_line
from .datfile import DatFile
from .grouping import build_marked_tree, render_marked_tree
from .metadata import is_release

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from .attributes import Edition
    from .metadata import Metadata, MetadataFilter

logger = logging.getLogger(__name__)

_STYLE_BY_MARK = {"+": "green", "~": "yellow", "-": "red"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Group, inspect, and filter No-Intro/Redump .dat files."
    )
    parser.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="Colorize output: 'auto' (default), 'always', or 'never'.",
    )
    add_log_arguments(parser)

    selection = parser.add_argument_group(
        "selection", "Which entries to keep (default: all)."
    )
    selection.add_argument(
        "--releases-only",
        action="store_true",
        help="Drop demos, prototypes/betas, early builds, non-game categories.",
    )
    selection.add_argument(
        "--has-english",
        action="store_true",
        help="Drop entries that have no English version.",
    )
    selection.add_argument(
        "-b",
        "--best-english",
        action="store_true",
        help=(
            "Keep one version per variant: the best English, or the original"
            " if none (unless --has-english drops it)."
        ),
    )

    output = parser.add_argument_group(
        "output", "What to emit (default: --tree)."
    )
    output.add_argument(
        "-t",
        "--tree",
        action="store_true",
        help="Print the grouped variant tree, marking kept/removed entries.",
    )
    output.add_argument(
        "-l",
        "--list",
        dest="show_list",
        action="store_true",
        help="Print a flat per-entry list, marking kept/removed entries.",
    )
    output.add_argument(
        "-o", "--output", help="Write the kept entries to this .dat file."
    )
    output.add_argument(
        "--name",
        help="Header name for the written dat (default: keep the original).",
    )
    output.add_argument(
        "--tags",
        action="store_true",
        help="List tags the parser did not recognize (candidates to support).",
    )
    output.add_argument(
        "--editions", action="store_true", help="List every edition seen."
    )
    output.add_argument(
        "--categories", action="store_true", help="List every category seen."
    )

    parser.add_argument("dat_file", help="Path to the source .dat file.")
    return parser


def _has_english(metadata: Metadata) -> bool:
    return bool(metadata.localization.english_priority())


def _content_filter(args: argparse.Namespace) -> MetadataFilter | None:
    """Predicate for the candidate set (content filters, no reduction)."""
    predicates: list[MetadataFilter] = []
    if args.releases_only:
        predicates.append(is_release)
    if args.has_english:
        predicates.append(_has_english)
    if not predicates:
        return None
    return lambda metadata: all(
        predicate(metadata) for predicate in predicates
    )


def _select_stems(args: argparse.Namespace, datfile: DatFile) -> set[str]:
    """The kept set: candidates, reduced to best English per variant if asked."""
    games = datfile.build_games(
        metadata_filter=is_release if args.releases_only else None
    )
    stems: set[str] = set()
    for game in games.values():
        if args.best_english:
            selected = (
                game.english_entities()
                if args.has_english
                else game.representative_entities()
            )
        elif args.has_english:
            selected = [
                metadata
                for metadata in game.versions
                if metadata.localization.english_priority()
            ]
        else:
            selected = game.versions
        stems.update(metadata.stem for metadata in selected)
    return stems


def _mark(metadata: Metadata, kept: set[str]) -> str:
    if metadata.stem not in kept:
        return "-"
    return "+" if _has_english(metadata) else "~"


def _stdout_is_terminal() -> bool:
    return sys.stdout.isatty()


def _print_summary(datfile: DatFile, kept: set[str]) -> None:
    # Only when stdout is a real terminal. If it is piped (e.g. to a pager),
    # writing this to stderr while the pager owns the screen scrambles its
    # display, and it would pollute redirected/captured output besides.
    if not _stdout_is_terminal():
        return
    removed = len(datfile.entries) - len(kept)
    print(f"{len(kept)} kept, {removed} removed", file=sys.stderr)


def _print_list(datfile: DatFile, kept: set[str]) -> None:
    for stem, metadata in datfile.entries.items():
        mark = _mark(metadata, kept)
        print_line(f"{mark} {stem}", style=_STYLE_BY_MARK[mark])
    _print_summary(datfile, kept)


def _print_tree(datfile: DatFile, kept: set[str]) -> None:
    for title, game in datfile.build_games().items():
        tree = build_marked_tree(
            title, game.versions, lambda metadata: _mark(metadata, kept)
        )
        for line in render_marked_tree(tree):
            print_line(line.text, style=line.style)
    _print_summary(datfile, kept)


def _print_editions(editions: set[Edition]) -> None:
    if editions:
        print("Editions:")
        for edition in sorted(editions):
            print(f"- {edition}")
        print()


def _print_unhandled(unhandled: dict[str, list[Metadata]]) -> None:
    if unhandled:
        print("Unhandled Tags:")
        for tag, tagged in unhandled.items():
            print(f"- {tag}")
            for metadata in tagged:
                print(f"  - {metadata.stem}")
        print()


def _print_categories(categories: set[str]) -> None:
    if categories:
        print("Categories:")
        for category in sorted(categories):
            print(f"- {category}")
        print()


def _print_surveys(
    metadata_list: Iterable[Metadata],
    *,
    show_tags: bool,
    show_editions: bool,
    show_categories: bool,
) -> None:
    editions: set[Edition] = set()
    unhandled: dict[str, list[Metadata]] = {}
    categories: set[str] = set()
    for metadata in metadata_list:
        if show_editions and metadata.entity.edition:
            editions.add(metadata.entity.edition)
        if show_tags and metadata.entity.unhandled_tags:
            key = str(sorted(metadata.entity.unhandled_tags.values))
            unhandled.setdefault(key, []).append(metadata)
        if show_categories and metadata.category:
            categories.add(metadata.category)
    _print_editions(editions)
    _print_unhandled(unhandled)
    _print_categories(categories)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(args=argv)
    configure_logging(args)
    configure_color(args.color)
    if args.name and not args.output:
        parser.error("--name requires -o/--output")

    datfile = DatFile(args.dat_file)
    kept = _select_stems(args, datfile)
    emitted = False
    if args.output:
        count = datfile.write(Path(args.output), kept=kept, name=args.name)
        print(f"Wrote {count} entries to {args.output}", file=sys.stderr)
        emitted = True
    if args.tags or args.editions or args.categories:
        _print_surveys(
            datfile.metadata(metadata_filter=_content_filter(args)),
            show_tags=args.tags,
            show_editions=args.editions,
            show_categories=args.categories,
        )
        emitted = True
    if args.show_list:
        _print_list(datfile, kept)
        emitted = True
    if args.tree or not emitted:
        _print_tree(datfile, kept)
    return 0
