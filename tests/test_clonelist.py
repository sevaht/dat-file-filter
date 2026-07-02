import json
from pathlib import Path

from dat_file_filter.clonelist import (
    available_systems,
    find_groups,
    load_groups,
)


def test_load_groups_uses_titles_and_supersets_skips_the_rest() -> None:
    text = json.dumps(
        {
            "variants": [
                {
                    "group": "Foo",
                    "titles": [
                        {"searchTerm": "Foo"},
                        {"searchTerm": "Foo (Japanese name)"},
                    ],
                    "supersets": [{"searchTerm": "Foo GOTY"}],
                },
                {"group": "Solo", "titles": [{"searchTerm": "Solo"}]},
                {
                    "group": "Comp",
                    "compilations": [
                        {"searchTerm": "Comp A"},
                        {"searchTerm": "Comp B"},
                    ],
                },
            ]
        }
    )
    # supersets join the group; the singleton and the compilation are dropped.
    assert load_groups(text) == [{"Foo", "Foo (Japanese name)", "Foo GOTY"}]


def _write_clonelist(path: Path, *terms: str) -> None:
    variant = {"titles": [{"searchTerm": t} for t in terms]}
    path.write_text(json.dumps({"variants": [variant]}), encoding="utf-8")


def test_find_groups_picks_longest_matching_system(tmp_path: Path) -> None:
    _write_clonelist(tmp_path / "Sony - PlayStation (Redump).json", "A", "B")
    _write_clonelist(tmp_path / "Sony - PlayStation 2 (Redump).json", "X", "Y")

    ps1 = find_groups(
        "Sony - PlayStation - Datfile (10758)", directory=tmp_path
    )
    assert ps1 == [{"A", "B"}]

    ps2 = find_groups("Sony - PlayStation 2 - Datfile", directory=tmp_path)
    assert ps2 == [{"X", "Y"}]


def test_find_groups_returns_none_on_no_match(tmp_path: Path) -> None:
    _write_clonelist(tmp_path / "Sega - Saturn (Redump).json", "A", "B")
    assert find_groups("Nintendo - Whatever", directory=tmp_path) is None


def test_available_systems_dedupes_and_sorts(tmp_path: Path) -> None:
    _write_clonelist(tmp_path / "Sega - Saturn (Redump).json", "A", "B")
    _write_clonelist(
        tmp_path / "Nintendo - Game Boy (No-Intro).json", "C", "D"
    )
    assert available_systems(tmp_path) == [
        "Nintendo - Game Boy",
        "Sega - Saturn",
    ]


def test_hash_manifest_is_not_treated_as_a_system(tmp_path: Path) -> None:
    _write_clonelist(tmp_path / "Sega - Saturn (Redump).json", "A", "B")
    (tmp_path / "hash.json").write_text(
        json.dumps({"Sega - Saturn (Redump).json": "deadbeef"}),
        encoding="utf-8",
    )
    # The integrity manifest is skipped: "hash" is not a system, and it is
    # never selected as a clone list.
    assert available_systems(tmp_path) == ["Sega - Saturn"]
    assert find_groups("hash", directory=tmp_path) is None


def test_bundled_available_systems_excludes_hash() -> None:
    assert "hash" not in available_systems()
