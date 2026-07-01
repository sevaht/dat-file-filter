"""Split a dat entry's name into its title and bracketed/parenthesized tags."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import chain
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class StemInfo:
    """A dat entry name decomposed into its title and its raw tags.

    Tags are the comma/plus-separated values found inside ``(...)`` or
    ``[...]`` groups; everything outside of groups forms the title.
    """

    title: str
    tags: list[str] = field(default_factory=list)

    _OPEN_TO_CLOSE: ClassVar[dict[str, str]] = {"[": "]", "(": ")"}
    _TOKEN_RE: ClassVar[re.Pattern[str]] = re.compile(
        r" *((?P<open>O)|(?P<close>C)) *| +".replace(r" ", r"[\s_]")
        # uses negative lookahead to exclude the kaomoji "(^^;"
        .replace(r"O", r"\[|\((?!\^\^;)").replace(r"C", r"[)\]]")
    )
    _TAG_COMMA_RE: ClassVar[re.Pattern[str]] = re.compile(r" *[,\+] *")

    @staticmethod
    def from_stem(stem: str) -> StemInfo:  # noqa: C901
        last_end = 0
        in_open_tag: str | None = None
        title_parts: list[str] = []
        tag_parts: list[str] = []
        tags: list[str] = []
        for match in chain(StemInfo._TOKEN_RE.finditer(stem), [None]):
            start = match.start() if match else len(stem)
            if start != last_end:
                segment = stem[last_end:start]
                parts = tag_parts if in_open_tag else title_parts
                parts.append(segment)
            if match:
                if symbol := match.group("open"):
                    if in_open_tag:
                        msg = f"nested groups: {stem}"
                        raise ValueError(msg)
                    in_open_tag = symbol
                elif symbol := match.group("close"):
                    if not in_open_tag:
                        msg = f"group closed but none open: {stem}"
                        raise ValueError(msg)
                    if symbol != StemInfo._OPEN_TO_CLOSE[in_open_tag]:
                        msg = f"mismatched close tag: {stem}"
                        raise ValueError(msg)
                    in_open_tag = None
                    if tag_parts:
                        full_tag = " ".join(tag_parts)
                        tags.extend(
                            tag
                            for tag in StemInfo._TAG_COMMA_RE.split(full_tag)
                            if tag
                        )
                        tag_parts = []
                last_end = match.end()
            elif in_open_tag:
                msg = f"unterminated group: {stem}"
                raise ValueError(msg)
        return StemInfo(title=" ".join(title_parts), tags=tags)

    @staticmethod
    def from_path(path: Path) -> StemInfo:
        return StemInfo.from_stem(path.stem)
