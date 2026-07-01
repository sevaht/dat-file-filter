"""Immutable value objects describing one release of a game.

Each attribute knows how to sort itself (``order=True``), test whether it holds
any information (``__bool__``), and render a human-readable label (``__str__``)
for reports. ``Entity`` bundles the attributes that identify a distinct
variant; localization is kept separate because the "same" variant can exist in
several regions/languages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .enums import Language, Region

if TYPE_CHECKING:
    import datetime

# english_priority() returns 0 for "no English"; for sorting we want those to
# come *after* every English rank, so map 0 to this large rank.
NO_ENGLISH_SORT_RANK = 1 << 30


@dataclass(frozen=True, eq=True)
class Date:
    date: datetime.date | None = None

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Date):
            return NotImplemented
        # Treat None as less than any date.
        return (self.date is None, self.date) < (
            other.date is None,
            other.date,
        )

    def __bool__(self) -> bool:
        return bool(self.date)

    def __str__(self) -> str:
        return str(self.date) if self.date else ""


@dataclass(frozen=True, eq=True, order=True)
class Version:
    version: str = ""
    revision: str = ""
    date: Date = field(default_factory=lambda: Date(None))

    def __bool__(self) -> bool:
        return bool(self.version or self.revision or self.date)

    def __str__(self) -> str:
        output: list[str] = []
        if self.version:
            output.append(f"v{self.version}")
        if self.revision:
            if not self.revision[0].isdigit():
                output.append(f"Rev {self.revision}")
            else:
                output.append(f"r{self.revision}")
        if self.date:
            output.append(f"({self.date})")
        if output:
            return " ".join(output)
        return "<Versionless>"


@dataclass(frozen=True, eq=True, order=True)
class Edition:
    arcade: bool = False
    prerelease: str = ""
    demo: str = ""
    early: str = ""
    debug: bool = False
    alternate: int = 0
    wii: bool = False
    switch: bool = False
    steam: bool = False
    virtual_console: bool = False
    classic_mini: bool = False
    nintendo_power: bool = False  # updated versions of certain Japanese games

    def __bool__(self) -> bool:
        return bool(
            self.arcade
            or self.prerelease
            or self.demo
            or self.early
            or self.debug
            or self.alternate
            or self.wii
            or self.switch
            or self.steam
            or self.virtual_console
            or self.classic_mini
            or self.nintendo_power
        )

    def __str__(self) -> str:  # noqa: C901, PLR0912
        output: list[str] = []
        if self.arcade:
            output.append("(Arcade)")
        if self.prerelease:
            output.append(f"[{self.prerelease}]")
        if self.demo:
            output.append(f"[{self.demo}]")
        if self.early:
            output.append(f"[{self.early}]")
        if self.debug:
            output.append("[Debug]")
        if self.alternate:
            if self.alternate > 1:
                output.append(f"(Alt {self.alternate})")
            else:
                output.append("(Alt)")
        if self.wii:
            output.append("(Wii)")
        if self.switch:
            output.append("(Switch)")
        if self.steam:
            output.append("(Steam)")
        if self.virtual_console:
            output.append("(Virtual Console)")
        if self.classic_mini:
            output.append("(Classic Mini)")
        if self.nintendo_power:
            output.append("(Nintendo Power)")
        if output:
            return " ".join(output)
        return "<Editionless>"


@dataclass(frozen=True, eq=True, order=True)
class Disc:
    name: str = ""
    number: int | None = None

    def __bool__(self) -> bool:
        return bool(self.name or self.number)

    def __str__(self) -> str:
        output: list[str] = []
        if self.name:
            output.append(self.name)
        if self.number:
            output.append(f"Disc {self.number}")
        if output:
            inner = ", ".join(output)
            return f"({inner})"
        return "<Discless>"


@dataclass(frozen=True, eq=True, order=True)
class Localization:
    _sort_key: tuple[int, tuple[Region, ...], tuple[Language, ...]] = field(
        init=False, compare=True, repr=False
    )
    regions: frozenset[Region] = field(
        default_factory=frozenset, compare=False
    )
    languages: frozenset[Language] = field(
        default_factory=frozenset, compare=False
    )

    def __post_init__(self) -> None:
        priority = self.english_priority()
        sort_key: tuple[int, tuple[Region, ...], tuple[Language, ...]] = (
            # English first (best rank first); no English (0) sorts last.
            priority or NO_ENGLISH_SORT_RANK,
            tuple(sorted(self.regions)),
            tuple(sorted(self.languages)),
        )
        # object.__setattr__ because the dataclass is frozen.
        object.__setattr__(self, "_sort_key", sort_key)

    def __bool__(self) -> bool:
        return bool(self.regions or self.languages)

    def english_priority(self) -> int:  # noqa: C901, PLR0911
        """Rank English availability; lower is better, 0 means none."""
        is_american_english = Language.AMERICAN_ENGLISH in self.languages
        is_english = Language.ENGLISH in self.languages
        is_british_english = Language.BRITISH_ENGLISH in self.languages
        any_english = is_american_english or is_english or is_british_english
        not_only_nonenglish = not self.languages or any_english
        if Region.USA in self.regions and not_only_nonenglish:
            return 1
        if is_american_english:
            return 2
        if is_english:
            return 3
        if is_british_english:
            return 4
        if not_only_nonenglish:
            if Region.CANADA in self.regions:
                return 5
            if Region.UNITED_KINGDOM in self.regions:
                return 6
            if Region.AUSTRALIA in self.regions:
                return 7
            if Region.NEW_ZEALAND in self.regions:
                return 8
            if Region.EUROPE in self.regions:
                return 9
        return 0

    def __str__(self) -> str:
        output: list[str] = []
        if self.regions:
            joined = ", ".join(sorted(region.value for region in self.regions))
            output.append(f"[{joined}]")
        if self.languages:
            joined = ", ".join(
                sorted(language.value for language in self.languages)
            )
            output.append(f"[{joined}]")
        if output:
            return " ".join(output)
        return "<Unlocalized>"


@dataclass(frozen=True, eq=True, order=True)
class Tags:
    _sort_key: tuple[str, ...] = field(init=False, compare=True, repr=False)
    values: frozenset[str] = field(default_factory=frozenset, compare=False)

    def __post_init__(self) -> None:
        sort_key: tuple[str, ...] = tuple(sorted(self.values))
        # object.__setattr__ because the dataclass is frozen.
        object.__setattr__(self, "_sort_key", sort_key)

    def __bool__(self) -> bool:
        return bool(self.values)

    def __str__(self) -> str:
        if self.values:
            return " ".join(f"[{value}]" for value in sorted(self.values))
        return "<Untagged>"


@dataclass(frozen=True, eq=True, order=True)
class Entity:
    """The attributes that together identify a distinct variant of a game."""

    edition: Edition = field(default_factory=Edition)
    version: Version = field(default_factory=Version)
    disc: Disc = field(default_factory=Disc)
    unhandled_tags: Tags = field(default_factory=Tags)

    def __bool__(self) -> bool:
        return bool(
            self.edition or self.version or self.disc or self.unhandled_tags
        )

    def __str__(self) -> str:
        output: list[str] = []
        if self.edition:
            output.append(str(self.edition))
        if self.version:
            output.append(str(self.version))
        if self.disc:
            output.append(str(self.disc))
        if self.unhandled_tags:
            output.append(str(self.unhandled_tags))
        if output:
            return " ".join(output)
        return "<Default>"
