import re
from pathlib import Path

from dat_file_filter.datfile import DatFile
from dat_file_filter.metadata import is_release

_SAMPLE_DAT = """<?xml version="1.0"?>
<datafile>
  <header>
    <name>Sample</name>
    <description>Sample</description>
  </header>
  <game name="Cool Game (USA)">
    <description>Cool Game (USA)</description>
    <category>Games</category>
  </game>
  <game name="Cool Game (Japan) (Ja)">
    <description>Cool Game (Japan) (Ja)</description>
    <category>Games</category>
  </game>
  <game name="Cool Game (Demo) (USA)">
    <description>Cool Game (Demo) (USA)</description>
    <category>Demos</category>
  </game>
</datafile>
"""

# Two entries linked by clone id (the child clones the parent) plus a DOCTYPE.
_CLONE_DAT = """<?xml version="1.0"?>
<!DOCTYPE datafile PUBLIC "-//Logiqx//DTD Datafile//EN" "http://d/d.dtd">
<datafile>
  <header>
    <name>Sample</name>
  </header>
  <game name="Parent (USA)" id="0001">
    <description>Parent (USA)</description>
  </game>
  <game name="Child (Japan)" id="0002" cloneofid="0001">
    <description>Child (Japan)</description>
  </game>
</datafile>
"""


# A clone family whose parent (0039) is the entry that best-english drops.
_FAMILY_DAT = """<?xml version="1.0"?>
<datafile>
  <header><name>Sample</name></header>
  <game name="Game (Europe)" id="0039">
    <description>Game (Europe)</description>
  </game>
  <game name="Game (USA)" id="0040" cloneofid="0039">
    <description>Game (USA)</description>
  </game>
  <game name="Game (USA) (Beta)" id="0041" cloneofid="0039">
    <description>Game (USA) (Beta)</description>
  </game>
</datafile>
"""

# Two entries the tool groups by title alone (no ids, no clone links).
_TITLE_DAT = """<?xml version="1.0"?>
<datafile>
  <header><name>Sample</name></header>
  <game name="Thing (USA)">
    <description>Thing (USA)</description>
  </game>
  <game name="Thing (Japan)">
    <description>Thing (Japan)</description>
  </game>
</datafile>
"""


def _write_dat(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "sample.dat"
    path.write_text(text, encoding="utf-8")
    return path


def _block(text: str, name: str) -> str | None:
    match = re.search(
        re.escape(f'<game name="{name}"') + r".*?</game>", text, re.DOTALL
    )
    return match.group(0) if match else None


def test_parse_reads_header_and_entries(tmp_path: Path) -> None:
    datfile = DatFile(_write_dat(tmp_path, _SAMPLE_DAT))
    assert datfile.name == "Sample"
    assert len(datfile.entries) == 3


def test_grouping_collapses_variants_into_one_game(tmp_path: Path) -> None:
    datfile = DatFile(_write_dat(tmp_path, _SAMPLE_DAT))
    games = datfile.build_games()
    assert len(games) == 1
    (game,) = games.values()
    assert len(game.versions) == 3


def test_metadata_filter_drops_demo(tmp_path: Path) -> None:
    datfile = DatFile(_write_dat(tmp_path, _SAMPLE_DAT))
    games = datfile.build_games(metadata_filter=is_release)
    (game,) = games.values()
    assert len(game.versions) == 2
    assert all(not m.entity.edition.demo for m in game.versions)


def test_passthrough_round_trips(tmp_path: Path) -> None:
    datfile = DatFile(_write_dat(tmp_path, _SAMPLE_DAT))
    output = tmp_path / "full.dat"
    count = datfile.write(output, kept=set(datfile.entries))
    assert count == len(datfile.entries)
    reparsed = DatFile(output)
    assert set(reparsed.entries) == set(datfile.entries)
    assert reparsed.name == "Sample"  # header preserved without a name


def test_filtered_matches_passthrough_except_removed(tmp_path: Path) -> None:
    datfile = DatFile(_write_dat(tmp_path, _CLONE_DAT))
    full = tmp_path / "full.dat"
    datfile.write(full, kept=set(datfile.entries))
    subset = tmp_path / "subset.dat"
    datfile.write(subset, kept={"Parent (USA)"})

    full_text = full.read_text(encoding="utf-8")
    subset_text = subset.read_text(encoding="utf-8")
    # The kept block is serialized identically whether or not others are kept.
    assert _block(subset_text, "Parent (USA)") == _block(
        full_text, "Parent (USA)"
    )
    assert "Child (Japan)" not in subset_text
    assert "Child (Japan)" in full_text
    # DOCTYPE is preserved in the canonical output.
    assert "<!DOCTYPE datafile" in subset_text


def test_write_strips_dangling_cloneofid(tmp_path: Path) -> None:
    datfile = DatFile(_write_dat(tmp_path, _CLONE_DAT))
    output = tmp_path / "out.dat"
    # Keep only the child, whose parent (0001) is removed.
    count = datfile.write(output, kept={"Child (Japan)"})
    assert count == 1
    text = output.read_text(encoding="utf-8")
    assert "Parent (USA)" not in text
    assert "cloneofid" not in text  # dangling reference dropped
    assert 'id="0002"' in text  # own id kept
    assert set(DatFile(output).entries) == {"Child (Japan)"}


def test_write_keeps_cloneofid_when_parent_kept(tmp_path: Path) -> None:
    datfile = DatFile(_write_dat(tmp_path, _CLONE_DAT))
    output = tmp_path / "out.dat"
    count = datfile.write(output, kept={"Parent (USA)", "Child (Japan)"})
    assert count == 2
    assert 'cloneofid="0001"' in output.read_text(encoding="utf-8")


def test_title_does_not_bridge_two_clone_linked_games(tmp_path: Path) -> None:
    # Two distinct games, each grouped by clone id, share the generic title
    # "Bar" on one entry. Title matching must not merge them.
    dat = """<?xml version="1.0"?>
<datafile>
  <header><name>Sample</name></header>
  <game name="Foo (USA)" id="1"><description>Foo (USA)</description></game>
  <game name="Bar (Japan)" id="2" cloneofid="1">
    <description>Bar (Japan)</description>
  </game>
  <game name="Baz (USA)" id="3"><description>Baz (USA)</description></game>
  <game name="Bar (Europe)" id="4" cloneofid="3">
    <description>Bar (Europe)</description>
  </game>
</datafile>
"""
    games = DatFile(_write_dat(tmp_path, dat)).build_games()
    assert len(games) == 2
    assert all(len(game.versions) == 2 for game in games.values())


def test_loose_entry_joins_its_game_by_title(tmp_path: Path) -> None:
    # Disc 3 has no clone id but shares the title with the clone-linked discs,
    # so the title fallback still pulls it into the same game.
    dat = """<?xml version="1.0"?>
<datafile>
  <header><name>Sample</name></header>
  <game name="Multi (USA) (Disc 1)" id="1">
    <description>Multi (USA) (Disc 1)</description>
  </game>
  <game name="Multi (USA) (Disc 2)" id="2" cloneofid="1">
    <description>Multi (USA) (Disc 2)</description>
  </game>
  <game name="Multi (USA) (Disc 3)">
    <description>Multi (USA) (Disc 3)</description>
  </game>
</datafile>
"""
    games = DatFile(_write_dat(tmp_path, dat)).build_games()
    assert len(games) == 1
    (game,) = games.values()
    assert len(game.versions) == 3


def test_title_groups_merge_differently_named_entries(tmp_path: Path) -> None:
    dat = """<?xml version="1.0"?>
<datafile>
  <header><name>Sample</name></header>
  <game name="Alpha (USA)"><description>Alpha (USA)</description></game>
  <game name="Beta (Japan)"><description>Beta (Japan)</description></game>
</datafile>
"""
    datfile = DatFile(_write_dat(tmp_path, dat))
    # Different titles, no clone ids: two separate games.
    assert len(datfile.build_games()) == 2
    # A clone-list group linking the two titles merges them into one.
    games = datfile.build_games(title_groups=[{"Alpha", "Beta"}])
    assert len(games) == 1
    (game,) = games.values()
    assert {m.title for m in game.versions} == {"Alpha", "Beta"}


def test_write_repoints_clones_when_parent_removed(tmp_path: Path) -> None:
    datfile = DatFile(_write_dat(tmp_path, _FAMILY_DAT))
    output = tmp_path / "out.dat"
    # Drop the Europe parent (0039); keep the two USA variants.
    datfile.write(output, kept={"Game (USA)", "Game (USA) (Beta)"})
    text = output.read_text(encoding="utf-8")
    assert "0039" not in text  # old parent gone, nothing dangles to it
    # The first-in-tree survivor (editionless USA) becomes the new parent...
    assert '<game name="Game (USA)" id="0040">' in text
    # ...and its Beta sibling now clones it.
    assert 'cloneofid="0040"' in text


def test_write_creates_clone_link_for_title_group(tmp_path: Path) -> None:
    datfile = DatFile(_write_dat(tmp_path, _TITLE_DAT))
    output = tmp_path / "out.dat"
    datfile.write(output, kept=set(datfile.entries))
    text = output.read_text(encoding="utf-8")
    # Grouped by title alone with no ids in the source: the tool assigns ids
    # and links them, creating a clone group that did not exist before.
    assert text.count("cloneofid=") == 1
    assert text.count(" id=") == 2
    # The best English entry (USA) is the parent; Japan clones it.
    usa = _block(text, "Thing (USA)") or ""
    japan = _block(text, "Thing (Japan)") or ""
    assert "cloneofid" not in usa
    usa_id = re.search(r'\bid="([^"]*)"', usa)
    assert usa_id is not None
    assert f'cloneofid="{usa_id.group(1)}"' in japan
    assert set(DatFile(output).entries) == set(datfile.entries)


def test_write_renames_header_only_with_name(tmp_path: Path) -> None:
    datfile = DatFile(_write_dat(tmp_path, _CLONE_DAT))
    output = tmp_path / "out.dat"
    datfile.write(output, kept={"Parent (USA)"}, name="Renamed")
    assert DatFile(output).name == "Renamed"
