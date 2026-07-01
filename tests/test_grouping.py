from collections.abc import Callable

from dat_file_filter.grouping import (
    MarkedLine,
    build_marked_tree,
    render_marked_tree,
)
from dat_file_filter.metadata import Metadata


def _lines(
    game_title: str, stems: list[str], mark_for: Callable[[Metadata], str]
) -> list[MarkedLine]:
    versions = [Metadata.from_stem(stem) for stem in stems]
    return render_marked_tree(
        build_marked_tree(game_title, versions, mark_for)
    )


def _text(game_title: str, stems: list[str]) -> str:
    return "\n".join(
        line.text for line in _lines(game_title, stems, lambda _metadata: "+")
    )


def test_uniformly_empty_fields_are_omitted() -> None:
    # No entry has an edition/version/tag/disc: only localization differs.
    out = _text("Game", ["Game (USA)", "Game (Japan) (Ja)"])
    assert "<Editionless>" not in out
    assert "<Versionless>" not in out
    assert "<Untagged>" not in out
    assert "<Discless>" not in out
    assert "[USA]" in out
    assert "[Japan]" in out


def test_placeholder_shown_when_some_entry_defines_field() -> None:
    # One entry has a disc, so its discless sibling is flagged <Discless>.
    out = _text("Game", ["Game (USA)", "Game (Disc 2) (USA)"])
    assert "<Discless>" in out
    assert "(Disc 2)" in out
    # Fields that are empty for every entry are still omitted.
    assert "<Editionless>" not in out


def test_marked_tree_is_tri_state() -> None:
    stems = ["Game (USA)", "Game (Japan) (Ja)", "Game (France) (Fr)"]
    kept = {"Game (USA)", "Game (France) (Fr)"}

    def mark_for(metadata: Metadata) -> str:
        if metadata.stem not in kept:
            return "-"
        return "+" if metadata.localization.english_priority() else "~"

    lines = _lines("Game", stems, mark_for)
    usa = next(line for line in lines if "[USA]" in line.text)
    assert usa.text.startswith("+")
    assert usa.style == "green"

    japan = next(line for line in lines if "[Japan]" in line.text)
    assert japan.text.startswith("-")
    assert japan.style == "red"

    # Kept, but no English available -> yellow.
    france = next(line for line in lines if "[France]" in line.text)
    assert france.text.startswith("~")
    assert france.style == "yellow"

    # The game header line has a blank gutter and no color.
    header = next(line for line in lines if line.text.strip() == "Game")
    assert header.style is None
    assert header.text.startswith(" ")
