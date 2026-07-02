from dat_file_filter.enums import Language, Region
from dat_file_filter.metadata import Metadata, is_release


def test_localization_extraction() -> None:
    metadata = Metadata.from_stem("Some Game (Japan) (En,Ja)")
    assert metadata.title == "Some Game"
    assert metadata.localization.regions == frozenset({Region.JAPAN})
    assert metadata.localization.languages == frozenset(
        {Language.ENGLISH, Language.JAPANESE}
    )


def test_disc_and_version_extraction() -> None:
    disc = Metadata.from_stem("Some Game (Disc 2) (USA)")
    assert disc.entity.disc.number == 2
    assert disc.localization.regions == frozenset({Region.USA})

    revision = Metadata.from_stem("Some Game (Rev 1) (USA)")
    assert revision.entity.version.revision == "1"


def test_demo_edition_and_metadata_filter() -> None:
    demo = Metadata.from_stem("Some Game (Demo) (USA)")
    assert demo.entity.edition.demo
    assert not is_release(demo)

    release = Metadata.from_stem("Some Game (USA)")
    assert is_release(release)


def test_unhandled_tag_is_recorded() -> None:
    metadata = Metadata.from_stem("Some Game (Frobnicate) (USA)")
    assert "Frobnicate" in metadata.entity.unhandled_tags.values


def test_english_priority_orders_usa_first() -> None:
    usa = Metadata.from_stem("Some Game (USA)")
    japan = Metadata.from_stem("Some Game (Japan) (Ja)")
    assert usa.localization.english_priority() > 0
    assert japan.localization.english_priority() == 0


def test_region_implied_english_ranking() -> None:
    def priority(stem: str) -> int:
        return Metadata.from_stem(stem).localization.english_priority()

    # A bare (World) release is worldwide English, ranked just below the
    # explicit English-language tags and ahead of the other regions.
    world = priority("Some Game (World)")
    assert world > 0
    # Monolingual-English regions outrank the "assumed English" multilingual
    # ones; Canada and Europe (bilingual/multilingual) sort last.
    assert (
        priority("Some Game (USA)")
        < world
        < priority("Some Game (UK)")
        < priority("Some Game (Canada)")
        < priority("Some Game (Europe)")
    )


def test_non_english_language_tag_overrides_region() -> None:
    # An explicit non-English-only language list rules out region-implied
    # English, even for otherwise-English regions.
    assert (
        Metadata.from_stem(
            "Some Game (World) (Ja)"
        ).localization.english_priority()
        == 0
    )
    assert (
        Metadata.from_stem(
            "Some Game (Canada) (Fr)"
        ).localization.english_priority()
        == 0
    )
