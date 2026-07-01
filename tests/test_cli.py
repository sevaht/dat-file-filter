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
    assert "1 kept, 2 removed" in captured.err


def test_no_english_kept_entry_is_yellow(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # No selection: everything is kept, so the Japanese-only entry is kept but
    # flagged as having no English (~), while USA entries are +.
    dat = _write(tmp_path)
    code = main(["--color", "never", "--list", dat])
    assert code == 0
    out = capsys.readouterr().out
    assert "~ Cool Game (Japan) (Ja)" in out
    assert "+ Cool Game (USA)" in out


def test_default_output_is_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dat = _write(tmp_path)
    code = main(["--color", "never", dat])
    assert code == 0
    out = capsys.readouterr().out
    assert "Cool Game" in out  # game header line
    assert "[USA]" in out  # a leaf line


def test_output_writes_filtered_dat(tmp_path: Path) -> None:
    dat = _write(tmp_path)
    output = tmp_path / "out.dat"
    code = main(["--releases-only", "--best-english", "-o", str(output), dat])
    assert code == 0
    text = output.read_text(encoding="utf-8")
    assert "Cool Game (USA)" in text
    assert "Demo" not in text


def test_name_requires_output(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["--name", "X", _write(tmp_path)])
