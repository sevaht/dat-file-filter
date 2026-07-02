"""Tag parsing: turn a single raw tag string into a recognized attribute.

A :class:`PatternParser` wraps a compiled regex plus an extractor that pulls
the meaningful value out of a match. A :class:`TagMatcher` is a stateful,
single-slot consumer built from a parser: it remembers the first value it
accepts and rejects conflicting duplicates. ``Metadata.from_stem`` runs a raw
tag through an ordered set of matchers to classify it.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import KW_ONLY, dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from re import Match


def _full_tag_extractor(match: Match[str]) -> str:
    return match.string


@dataclass
class PatternParser:
    """A compiled pattern plus a function that extracts its value."""

    pattern: re.Pattern[str]
    extractor: Callable[[Match[str]], str] = _full_tag_extractor

    def matcher(self, *, allow_duplicates: bool = False) -> TagMatcher:
        return TagMatcher(self, allow_duplicates=allow_duplicates)

    @classmethod
    def from_tags(
        cls,
        tags: list[str],
        extractor: Callable[[Match[str]], str] = _full_tag_extractor,
        *,
        case_sensitive: bool = False,
    ) -> PatternParser:
        return cls(
            re.compile(
                "|".join(re.escape(tag) for tag in tags),
                0 if case_sensitive else re.IGNORECASE,
            ),
            extractor,
        )

    def __call__(self, tag: str) -> str:
        if match := self.pattern.fullmatch(tag):
            return self.extractor(match)
        return ""


@dataclass
class TagMatcher:
    """A single-slot consumer of tags produced by a :class:`PatternParser`."""

    parser: PatternParser
    value: str = ""
    _: KW_ONLY
    allow_duplicates: bool = False

    def __call__(self, tag: str) -> bool:
        if value := self.parser(tag):
            if self.value:
                if not self.allow_duplicates:
                    msg = f'Multiple "{tag}" equivalent tags'
                    raise ValueError(msg)
                if value != self.value:
                    msg = (
                        f'Multiple "{tag}" equivalent tags (allowed), but'
                        " conflicting values encountered:"
                        f' "{self.value}" != "{value}"'
                    )
                    raise ValueError(msg)
            self.value = value
            return True
        return False

    def __bool__(self) -> bool:
        return bool(self.value)

    def __str__(self) -> str:
        return self.value

    def __int__(self) -> int:
        return int(self.value or 0)


_EARLY_ROMAN_NUMERALS = [
    "I",
    "II",
    "III",
    "IV",
    "V",
    "VI",
    "VII",
    "VIII",
    "IX",
    "X",
]
_EARLY_ROMAN_NUMERALS.extend([f"X{value}" for value in _EARLY_ROMAN_NUMERALS])
_EARLY_JAPANESE_NUMBERS: list[list[str]] = [
    ["ichi"],
    ["ni"],
    ["san"],
    ["shi", "yon"],
    ["go"],
    ["roku"],
    ["shichi", "nana"],
    ["hachi"],
    ["kyū", "ku", "kyu"],
    ["jū", "ju"],
]
_ROMAN_OR_JAPANESE_NUMBERS = (
    "|".join(_EARLY_ROMAN_NUMERALS)
    + "|"
    + "|".join(
        re.escape(item)
        for sublist in _EARLY_JAPANESE_NUMBERS
        for item in sublist
    )
)


def disc_number_to_int(number: str) -> str:
    """Normalize a disc number (digit, letter, roman, or Japanese) to a str."""
    if number.isdigit():
        return number
    try:
        # Check before alpha because single-character roman numerals overlap;
        # must already be uppercase to count as a roman numeral.
        return str(_EARLY_ROMAN_NUMERALS.index(number) + 1)
    except ValueError:
        pass
    number = number.lower()
    if len(number) == 1 and number.isalpha():
        return str(ord(number.lower()) - ord("a"))
    for index, values in enumerate(_EARLY_JAPANESE_NUMBERS):
        if number in values:
            return str(index + 1)
    return ""


DISC_NUMBER_PARSER = PatternParser(
    re.compile(
        r"cd (?P<name1>.+)|(?P<name2>.+)-hen|"  # -hen is Jp for "chapter"
        r"((?P<name3>.+) )?dis[ck]( (?P<number1>\d+|[A-Z]|"
        + _ROMAN_OR_JAPANESE_NUMBERS
        + rf"))?|(?P<number2>{_ROMAN_OR_JAPANESE_NUMBERS})",
        re.IGNORECASE,
    ),
    lambda match: disc_number_to_int(
        match.group("number1") or match.group("number2") or ""
    ),
)
DISC_NAME_PARSER = PatternParser(
    DISC_NUMBER_PARSER.pattern,
    lambda match: (
        match.group("name1")
        or match.group("name2")
        or match.group("name3")
        or ""
    ),
)
DEMO_PARSER = PatternParser(
    re.compile(
        r"(?P<name>(tech )?demo|(playable game )?preview( edition by .+)?"
        r"|.+ previews"  # Square Soft on PlayStation Previews
        r"|(taikenban )?sample( rom)?|(?P<trial>([^\s]+ )+)?trial)"
        r"( ((?P<iteration>\d+)|edition|version))?",
        re.IGNORECASE,
    )
)

EARLY_PARSER = PatternParser.from_tags(["early", "earlier"])
ARCADE_PARSER = PatternParser.from_tags(["arcade"])
WII_PARSER = PatternParser.from_tags(["wii"])
SWITCH_PARSER = PatternParser.from_tags(["switch", "switch online"])
STEAM_PARSER = PatternParser.from_tags(["steam"])
VIRTUAL_CONSOLE_PARSER = PatternParser.from_tags(["virtual console"])
CLASSIC_MINI_PARSER = PatternParser.from_tags(["classic mini"])
NINTENDO_POWER_PARSER = PatternParser.from_tags(["np"])
UNLICENSED_PARSER = PatternParser.from_tags(["unl", "unlicensed"])
BAD_DUMP_PARSER = PatternParser.from_tags(["b"])
DEBUG_PARSER = PatternParser.from_tags(["debug"])
ALTERNATE_PARSER = PatternParser(
    re.compile(r"alt( (?P<index>\d+))?", re.IGNORECASE),
    lambda match: match.group("index") or "1",
)
PRERELEASE_PARSER = PatternParser(
    re.compile(
        r"(?P<name>alpha|beta|([^\s]+ )?promo|(possible )?proto(type)?)"
        r"( (?P<iteration>\d+))?",
        re.IGNORECASE,
    )
)
DATE_PARSER = PatternParser(
    re.compile(
        r"(?P<year>\d{4})"
        r"([-.](?P<month>\d{1,2}|XX)"
        r"([-.](?P<day>\d{1,2}|XX))?)?",
        re.IGNORECASE,
    ),
    lambda match: datetime.date(
        int(match.group("year")),
        int(m) if (m := match.group("month")).lower() != "xx" else 1,
        int(d) if (d := match.group("day")).lower() != "xx" else 1,
    ).isoformat(),
)
REVISION_PARSER = PatternParser(
    re.compile(r"((Rev|Revision) |r)(?P<revision>[a-f0-9.]+)", re.IGNORECASE),
    lambda match: match.group("revision"),
)
VERSION_PARSER = PatternParser(
    re.compile(
        r"((?P<prefix>v|Ver|Version )(?P<value>[a-f0-9.]+))"
        r"|(?P<version>\.?(\d|[a-f]\d[^\s]*\d)[^\s]*)",
        re.IGNORECASE,
    ),
    lambda match: (
        match.group("value")
        if match.group("prefix")
        else match.group("version")
    ),
)
