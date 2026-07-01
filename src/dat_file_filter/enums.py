"""Language and region enumerations used to classify a release's audience."""

from __future__ import annotations

from enum import StrEnum, unique


@unique
class Language(StrEnum):
    AMERICAN_ENGLISH = "En-US"
    ENGLISH = "En"
    BRITISH_ENGLISH = "En-GB"
    FRENCH = "Fr"
    CANADIAN_FRENCH = "Fr-CA"
    GERMAN = "De"
    SPANISH = "Es"
    LATIN_AMERICAN_SPANISH = "Es-XL"
    ITALIAN = "It"
    DUTCH = "Nl"
    SWEDISH = "Sv"
    DANISH = "Da"
    JAPANESE = "Ja"
    NORWEGIAN = "No"
    FINNISH = "Fi"
    KOREAN = "Ko"
    RUSSIAN = "Ru"
    POLISH = "Pl"
    PORTUGESE = "Pt"
    BRAZILIAN_PORTUGESE = "Pt-BR"
    TURKISH = "Tr"
    ARABIC = "Ar"
    CHINESE = "Zh"
    SIMPLIFIED_CHINESE = "Zh-Hans"
    TRADITIONAL_CHINESE = "Zh-Hant"
    CZECH = "Cs"
    HINDI = "Hi"
    GREEK = "El"
    CATALAN = "Ca"
    CROATIAN = "Hr"
    HUNGARIAN = "Hu"


@unique
class Region(StrEnum):
    USA = "USA"
    UNITED_KINGDOM = "UK"
    AUSTRIA = "Austria"
    DENMARK = "Denmark"
    NORWAY = "Norway"
    EUROPE = "Europe"
    KOREA = "Korea"
    ASIA = "Asia"
    AUSTRALIA = "Australia"
    CHINA = "China"
    ITALY = "Italy"
    ISRAEL = "Israel"
    IRELAND = "Ireland"
    SCANDINAVIA = "Scandinavia"
    LATIN_AMERICA = "Latin America"
    TAIWAN = "Taiwan"
    BRAZIL = "Brazil"
    PORTUGAL = "Portugal"
    FRANCE = "France"
    GREECE = "Greece"
    SPAIN = "Spain"
    BELGIUM = "Belgium"
    NETHERLANDS = "Netherlands"
    CANADA = "Canada"
    GERMANY = "Germany"
    HONG_KONG = "Hong Kong"
    NEW_ZEALAND = "New Zealand"
    JAPAN = "Japan"
    SWEDEN = "Sweden"
    FINLAND = "Finland"
    POLAND = "Poland"
    WORLD = "World"
    RUSSIA = "Russia"


# Reverse lookups from a dat tag's literal text to the enum member.
LANGUAGE_BY_VALUE: dict[str, Language] = {
    member.value: member for member in Language
}
REGION_BY_VALUE: dict[str, Region] = {
    member.value: member for member in Region
}
