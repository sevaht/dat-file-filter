"""Assemble a :class:`Metadata` for one dat entry from its name and fields.

``Metadata.from_stem`` runs each raw tag through an ordered set of
:class:`~dat_file_filter.tags.TagMatcher` objects. The first top-level matcher
(or matcher group) to accept a tag consumes it; tags that no matcher claims and
that are not a known language or region are recorded as ``unhandled_tags`` so
parsing gaps can be surfaced.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from . import tags as t
from .attributes import (
    Date,
    Disc,
    Edition,
    Entity,
    Localization,
    Tags,
    Version,
)
from .enums import LANGUAGE_BY_VALUE, REGION_BY_VALUE, Language, Region
from .stem import StemInfo

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@dataclass(frozen=True, eq=True, order=True)
class Metadata:
    title: str = ""
    entity: Entity = field(default_factory=Entity)
    localization: Localization = field(default_factory=Localization)
    unlicensed: bool = False
    bad_dump: bool = False
    category: str = ""
    stem: str = ""
    game_id: str = ""
    clone_of_id: str = ""

    @staticmethod
    def from_stem(
        stem: str,
        *,
        category: str = "",
        game_id: str = "",
        clone_of_id: str = "",
    ) -> Metadata:
        stem_info = StemInfo.from_stem(stem)
        languages: set[Language] = set()
        regions: set[Region] = set()
        unhandled_tag_values: list[str] = []

        # Ordered matchers. When an entry is a list, every matcher in it is
        # tried even after one matches (so a disc name and number can both be
        # captured from one tag); once any matcher in a top-level entry
        # matches, no later top-level entry is tried for that tag.
        disc_name_matcher = t.DISC_NAME_PARSER.matcher()
        disc_number_matcher = t.DISC_NUMBER_PARSER.matcher(
            allow_duplicates=True
        )
        demo_matcher = t.DEMO_PARSER.matcher()
        early_matcher = t.EARLY_PARSER.matcher()
        debug_matcher = t.DEBUG_PARSER.matcher()
        arcade_matcher = t.ARCADE_PARSER.matcher()
        wii_matcher = t.WII_PARSER.matcher()
        switch_matcher = t.SWITCH_PARSER.matcher()
        steam_matcher = t.STEAM_PARSER.matcher()
        virtual_console_matcher = t.VIRTUAL_CONSOLE_PARSER.matcher()
        classic_mini_matcher = t.CLASSIC_MINI_PARSER.matcher()
        nintendo_power_matcher = t.NINTENDO_POWER_PARSER.matcher()
        unlicensed_matcher = t.UNLICENSED_PARSER.matcher()
        bad_dump_matcher = t.BAD_DUMP_PARSER.matcher()
        alternate_matcher = t.ALTERNATE_PARSER.matcher()
        date_matcher = t.DATE_PARSER.matcher()
        prerelease_matcher = t.PRERELEASE_PARSER.matcher()
        revision_matcher = t.REVISION_PARSER.matcher()
        version_matcher = t.VERSION_PARSER.matcher()
        tag_matchers: list[t.TagMatcher | list[t.TagMatcher]] = [
            [disc_name_matcher, disc_number_matcher],
            demo_matcher,
            early_matcher,
            debug_matcher,
            arcade_matcher,
            wii_matcher,
            switch_matcher,
            steam_matcher,
            virtual_console_matcher,
            classic_mini_matcher,
            nintendo_power_matcher,
            unlicensed_matcher,
            bad_dump_matcher,
            alternate_matcher,
            date_matcher,
            prerelease_matcher,
            revision_matcher,
            version_matcher,
        ]

        for tag in stem_info.tags:
            matched = False
            for entry in tag_matchers:
                group = entry if isinstance(entry, list) else [entry]
                for matcher in group:
                    if matcher(tag):
                        matched = True
                if matched:
                    break
            if matched:
                continue
            if language := LANGUAGE_BY_VALUE.get(tag):
                languages.add(language)
            elif region := REGION_BY_VALUE.get(tag):
                regions.add(region)
            elif not tag:
                msg = "Received blank tag; debug things!"
                raise RuntimeError(msg)
            else:
                unhandled_tag_values.append(tag)

        return Metadata(
            title=stem_info.title,
            entity=Entity(
                edition=Edition(
                    arcade=bool(arcade_matcher),
                    prerelease=str(prerelease_matcher),
                    demo=str(demo_matcher),
                    early=str(early_matcher),
                    debug=bool(debug_matcher),
                    alternate=int(alternate_matcher),
                    wii=bool(wii_matcher),
                    switch=bool(switch_matcher),
                    steam=bool(steam_matcher),
                    virtual_console=bool(virtual_console_matcher),
                    classic_mini=bool(classic_mini_matcher),
                    nintendo_power=bool(nintendo_power_matcher),
                ),
                version=Version(
                    version=str(version_matcher),
                    revision=str(revision_matcher),
                    date=Date(
                        datetime.date.fromisoformat(str(date_matcher))
                        if date_matcher
                        else None
                    ),
                ),
                disc=Disc(
                    name=str(disc_name_matcher),
                    number=int(disc_number_matcher),
                ),
                unhandled_tags=Tags(values=frozenset(unhandled_tag_values)),
            ),
            localization=Localization(
                regions=frozenset(regions), languages=frozenset(languages)
            ),
            stem=stem,
            unlicensed=bool(unlicensed_matcher),
            bad_dump=bool(bad_dump_matcher),
            category=category,  # forwarded from the dat, not parsed
            game_id=game_id,
            clone_of_id=clone_of_id,
        )

    @staticmethod
    def from_path(
        path: Path,
        *,
        category: str = "",
        game_id: str = "",
        clone_of_id: str = "",
    ) -> Metadata:
        return Metadata.from_stem(
            path.stem,
            category=category,
            game_id=game_id,
            clone_of_id=clone_of_id,
        )

    def __str__(self) -> str:
        output: list[str] = []
        if self.title:
            output.append(self.title)
        if self.entity:
            output.append(str(self.entity))
        if self.localization:
            output.append(str(self.localization))
        return " ".join(output)


# True for proper game releases; False for demos, prototypes/betas/alphas,
# early builds, and non-game categories (the "--releases-only" filter).
def is_release(metadata: Metadata) -> bool:
    return (
        not metadata.entity.edition.prerelease
        and not metadata.entity.edition.demo
        and not metadata.entity.edition.early
        and metadata.category.lower()
        not in {
            "demos",
            "demo",
            "preproduction",
            "educational",
            "audio",
            "video",
        }
    )


type MetadataFilter = Callable[[Metadata], bool]
