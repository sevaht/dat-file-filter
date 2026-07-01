"""A game: every parsed release variant grouped under one title."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .attributes import Entity
    from .metadata import Metadata


@dataclass
class Game:
    """All release variants of a single game.

    ``versions`` is sorted once at construction and treated as read-only
    thereafter, which makes the ``cached_property`` groupings below safe.
    """

    versions: list[Metadata] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.versions = sorted(self.versions)

    @cached_property
    def entity_to_metadata(self) -> dict[Entity, list[Metadata]]:
        """Group versions by their identifying :class:`Entity` (variant)."""
        grouped: dict[Entity, list[Metadata]] = {}
        for metadata in self.versions:
            grouped.setdefault(metadata.entity, []).append(metadata)
        return grouped

    @staticmethod
    def best_english_version(versions: list[Metadata]) -> Metadata | None:
        """Return the most English-preferred version, or ``None`` if none."""
        best: list[Metadata] = []
        best_priority = 0
        for metadata in versions:
            priority = metadata.localization.english_priority()
            if not priority:
                continue
            if not best or priority < best_priority:
                best = [metadata]
                best_priority = priority
            elif priority == best_priority:
                best.append(metadata)
        if not best:
            return None
        return min(best, key=lambda metadata: metadata.entity)

    def english_entities(self) -> list[Metadata]:
        """Best English version of each variant that has one.

        Variants with no English version are omitted entirely.
        """
        results: list[Metadata] = []
        for versions in self.entity_to_metadata.values():
            best = Game.best_english_version(versions)
            if best is not None:
                results.append(best)
        return results

    def representative_entities(self) -> list[Metadata]:
        """One version of every variant: best English, or the original.

        Like :meth:`english_entities`, but variants with no English version
        fall back to their original (best-sorted) version instead of being
        dropped, so no variant is lost.
        """
        results: list[Metadata] = []
        for versions in self.entity_to_metadata.values():
            best = Game.best_english_version(versions)
            results.append(best if best is not None else versions[0])
        return results

    @cached_property
    def english_title(self) -> str:
        """A representative English title, or ``""`` if none is available."""
        best = Game.best_english_version(self.versions)
        return best.title if best else ""
