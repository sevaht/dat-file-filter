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

from . import clonelist
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

    grouping = parser.add_argument_group(
        "grouping",
        "Cross-name grouping via clone lists. A matching clone list is required"
        " unless --no-clone-lists is given.",
    )
    grouping.add_argument(
        "--system",
        help=(
            "Clone-list system to use (see --list-clone-lists) instead of"
            " detecting it from the dat's name."
        ),
    )
    grouping.add_argument(
        "--no-clone-lists",
        action="store_true",
        help="Proceed without a clone list (group by title/clone id only).",
    )
    grouping.add_argument(
        "--list-clone-lists",
        action="store_true",
        help="List the available clone-list systems and exit.",
    )
    grouping.add_argument(
        "--clone-list-dir",
        help="Use clone lists from this directory instead of the bundled ones.",
    )
    grouping.add_argument(
        "--clone-list",
        help="Use this specific clone-list JSON file (overrides detection).",
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

    parser.add_argument(
        "dat_file", nargs="?", help="Path to the source .dat file."
    )
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


def _resolve_title_groups(
    args: argparse.Namespace, datfile: DatFile, parser: argparse.ArgumentParser
) -> list[set[str]] | None:
    if args.no_clone_lists:
        return None
    if args.clone_list:
        return clonelist.load_groups(
            Path(args.clone_list).read_text(encoding="utf-8")
        )
    directory = Path(args.clone_list_dir) if args.clone_list_dir else None
    if args.system:
        names = [args.system]
    else:
        names = [datfile.name, Path(args.dat_file).name]
    groups = clonelist.find_groups(*names, directory=directory)
    if groups is None:
        parser.error(
            "no clone list found for "
            + (f"system {args.system!r}" if args.system else "this dat")
            + "; choose one with --system (see --list-clone-lists), point to"
            " a file with --clone-list, or pass --no-clone-lists to proceed"
            " without one"
        )
    return groups


def _select_stems(
    args: argparse.Namespace,
    datfile: DatFile,
    title_groups: list[set[str]] | None,
) -> set[str]:
    """The kept set: candidates, reduced to best English per variant if asked."""
    games = datfile.build_games(
        metadata_filter=is_release if args.releases_only else None,
        title_groups=title_groups,
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


def _print_tree(
    datfile: DatFile, kept: set[str], title_groups: list[set[str]] | None
) -> None:
    games = datfile.build_games(title_groups=title_groups)
    for title, game in games.items():
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

    if args.list_clone_lists:
        directory = Path(args.clone_list_dir) if args.clone_list_dir else None
        for system in clonelist.available_systems(directory):
            print(system)
        return 0
    if not args.dat_file:
        parser.error("the dat_file argument is required")
    if args.name and not args.output:
        parser.error("--name requires -o/--output")

    datfile = DatFile(args.dat_file)
    title_groups = _resolve_title_groups(args, datfile, parser)
    kept = _select_stems(args, datfile, title_groups)
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
        _print_tree(datfile, kept, title_groups)
    return 0
