from dat_file_filter.game import Game
from dat_file_filter.metadata import Metadata


def test_english_entities_prefers_usa() -> None:
    usa = Metadata.from_stem("Game (USA)")
    japan = Metadata.from_stem("Game (Japan) (Ja)")
    # Same edition/version/disc -> one variant with two localizations.
    game = Game(versions=[japan, usa])
    assert game.english_entities() == [usa]
    assert game.representative_entities() == [usa]


def test_representative_falls_back_when_no_english() -> None:
    japan = Metadata.from_stem("Game (Japan) (Ja)")
    game = Game(versions=[japan])
    # No English available: dropped by english_entities, kept as the original
    # by representative_entities.
    assert game.english_entities() == []
    assert game.representative_entities() == [japan]
