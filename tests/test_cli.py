from pathlib import Path

import pytest

from dat_file_filter.application import main

_DAT = """<?xml version="1.0"?>
<datafile>
  <header><name>Sample</name></header>
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


def _write(tmp_path: Path) -> str:
    path = tmp_path / "sample.dat"
    path.write_text(_DAT, encoding="utf-8")
    return str(path)


def test_list_marks_kept_and_removed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dat = _write(tmp_path)
    code = main(
        [
            "--color",
            "never",
            "--no-clone-lists",
            "--releases-only",
            "--best-english",
            "--list",
            dat,
        ]
    )
    assert code == 0
    captured = capsys.readouterr()
    # Best English of the (single) variant is the USA release; the Japanese
    # copy collapses into it and the demo is dropped by --releases-only.
    assert "+ Cool Game (USA)" in captured.out
    assert "- Cool Game (Japan) (Ja)" in captured.out
    assert "- Cool Game (Demo) (USA)" in captured.out
    # The summary is suppressed when stdout is not a terminal (as under
    # capture), so it can't scramble a pager or pollute piped output.
    assert "kept" not in captured.err


def test_summary_shown_when_stdout_is_terminal(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "dat_file_filter.application._stdout_is_terminal", lambda: True
    )
    code = main(
        [
            "--color",
            "never",
            "--no-clone-lists",
            "--releases-only",
            "--best-english",
            "--list",
            _write(tmp_path),
        ]
    )
    assert code == 0
    assert "1 kept, 2 removed" in capsys.readouterr().err


def test_no_english_kept_entry_is_yellow(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # No selection: everything is kept, so the Japanese-only entry is kept but
    # flagged as having no English (~), while USA entries are +.
    dat = _write(tmp_path)
    code = main(["--color", "never", "--no-clone-lists", "--list", dat])
    assert code == 0
    out = capsys.readouterr().out
    assert "~ Cool Game (Japan) (Ja)" in out
    assert "+ Cool Game (USA)" in out


def test_keep_forces_an_otherwise_dropped_entry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dat = _write(tmp_path)
    code = main(
        [
            "--color",
            "never",
            "--no-clone-lists",
            "--releases-only",
            "--best-english",
            "--has-english",
            "--keep",
            "Cool Game (Japan) (Ja)",
            "--list",
            dat,
        ]
    )
    assert code == 0
    # Without --keep this no-English copy is dropped; --keep forces it back,
    # flagged * to show it survived specifically because it was kept.
    assert "* Cool Game (Japan) (Ja)" in capsys.readouterr().out


def test_keep_list_file_overrides_releases_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dat = _write(tmp_path)
    keep_file = tmp_path / "keep.txt"
    keep_file.write_text(
        "# keepers\n\nCool Game (Demo) (USA)\n", encoding="utf-8"
    )
    code = main(
        [
            "--color",
            "never",
            "--no-clone-lists",
            "--releases-only",
            "--best-english",
            "--keep-list",
            str(keep_file),
            "--list",
            dat,
        ]
    )
    assert code == 0
    # The demo is normally dropped by --releases-only; a keep overrides that
    # and marks it * (force-kept).
    assert "* Cool Game (Demo) (USA)" in capsys.readouterr().out


def test_unmatched_keep_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(
            [
                "--color",
                "never",
                "--no-clone-lists",
                "--keep",
                "Does Not Exist (USA)",
                "--list",
                _write(tmp_path),
            ]
        )


def test_default_output_is_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dat = _write(tmp_path)
    code = main(["--color", "never", "--no-clone-lists", dat])
    assert code == 0
    out = capsys.readouterr().out
    assert "Cool Game" in out  # game header line
    assert "[USA]" in out  # a leaf line


def test_output_writes_filtered_dat(tmp_path: Path) -> None:
    dat = _write(tmp_path)
    output = tmp_path / "out.dat"
    code = main(
        [
            "--no-clone-lists",
            "--releases-only",
            "--best-english",
            "-o",
            str(output),
            dat,
        ]
    )
    assert code == 0
    text = output.read_text(encoding="utf-8")
    assert "Cool Game (USA)" in text
    assert "Demo" not in text


def test_name_requires_output(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["--name", "X", _write(tmp_path)])


def test_errors_when_no_clone_list_matches(tmp_path: Path) -> None:
    # The synthetic "Sample" system matches no clone list; without an override
    # this is an error rather than a silent fallback.
    with pytest.raises(SystemExit):
        main(["--color", "never", "--list", _write(tmp_path)])


def test_list_clone_lists_lists_bundled_systems(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(["--list-clone-lists"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Sony - PlayStation" in out
    assert "Nintendo - Super Nintendo Entertainment System" in out


def test_system_flag_selects_bundled_list(tmp_path: Path) -> None:
    # --system loads a bundled list even though the dat's own name would not
    # match; the Sample titles simply aren't in it, so nothing errors.
    code = main(
        [
            "--color",
            "never",
            "--system",
            "Sony - PlayStation",
            "--list",
            _write(tmp_path),
        ]
    )
    assert code == 0
