from __future__ import annotations

import pytest

from tools.transliteration import (
    has_hangul,
    has_kana,
    has_kanji,
    japanese_place_variants,
    kana_place_prefix,
    latin_place_alias,
    romanize_hangul,
    romanize_kana,
    strip_korean_admin_suffix,
)


# ---------------------------------------------------------------------------
# Script detection
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "hangul", "kana", "kanji"),
    [
        ("서울", True, False, False),
        ("とうきょう", False, True, False),
        ("東京", False, False, True),
        ("東京とうきょう", False, True, True),
        ("London", False, False, False),
        ("", False, False, False),
    ],
)
def test_script_detection(text, hangul, kana, kanji):
    assert has_hangul(text) is hangul
    assert has_kana(text) is kana
    assert has_kanji(text) is kanji


# ---------------------------------------------------------------------------
# Hangul -> Revised Romanization
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("hangul", "expected"),
    [
        ("서울", "seoul"),
        ("부산", "busan"),
        ("대구", "daegu"),
        ("인천", "incheon"),
        ("광주", "gwangju"),
        ("대전", "daejeon"),
        ("울산", "ulsan"),
        ("수원", "suwon"),
        ("성남", "seongnam"),
        ("고양", "goyang"),
        ("용인", "yongin"),
        ("청주", "cheongju"),
        ("전주", "jeonju"),
        ("포항", "pohang"),
        ("경주", "gyeongju"),
        ("원주", "wonju"),
        ("속초", "sokcho"),
        ("여수", "yeosu"),
        ("목포", "mokpo"),
        ("안산", "ansan"),
        ("김해", "gimhae"),
        ("구미", "gumi"),
        ("남양", "namyang"),
        ("일산", "ilsan"),
        ("부천", "bucheon"),
        ("평택", "pyeongtaek"),
        ("안성", "anseong"),
        ("진주", "jinju"),
        ("나주", "naju"),
        ("춘천", "chuncheon"),
        ("창원", "changwon"),
        ("천안", "cheonan"),
        ("제주", "jeju"),
    ],
)
def test_romanize_hangul(hangul, expected):
    assert romanize_hangul(hangul) == expected


def test_romanize_hangul_known_deviation():
    # The upstream index spells this place "gangneung" -- the ㄹ is silent there,
    # which is a pronunciation quirk rather than a romanization rule.
    assert romanize_hangul("강릉") == "ganglung"


def test_romanize_hangul_keeps_non_hangul():
    assert romanize_hangul("Seoul") == "Seoul"
    assert romanize_hangul("") == ""


def test_strip_korean_admin_suffix():
    assert strip_korean_admin_suffix("수원시") == "수원"
    assert strip_korean_admin_suffix("성남시") == "성남"
    assert strip_korean_admin_suffix("제주도") == "제주"
    assert strip_korean_admin_suffix("서울") == "서울"
    assert strip_korean_admin_suffix("구") == "구"


# ---------------------------------------------------------------------------
# Kana -> Hepburn
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kana", "expected"),
    [
        ("とうきょう", "tokyo"),
        ("さっぽろ", "sapporo"),
        ("きょうと", "kyoto"),
        ("おおさか", "osaka"),
        ("よこはま", "yokohama"),
        ("なごや", "nagoya"),
        ("ふくおか", "fukuoka"),
        ("せんだい", "sendai"),
        ("こうべ", "kobe"),
        ("しんじゅく", "shinjuku"),
        ("ひらがな", "hiragana"),
        ("カタカナ", "katakana"),
    ],
)
def test_romanize_kana(kana, expected):
    assert romanize_kana(kana) == expected


def test_romanize_kana_keeps_non_kana():
    assert romanize_kana("Tokyo") == "Tokyo"
    assert romanize_kana("") == ""


# ---------------------------------------------------------------------------
# Japanese place-name variants
# ---------------------------------------------------------------------------
def test_japanese_place_variants():
    assert japanese_place_variants("横浜") == ["横浜市", "横浜都"]
    assert japanese_place_variants("東京") == ["東京市", "東京都"]
    # 京都 is a city name that happens to end in the same character as 東京都.
    assert japanese_place_variants("京都") == ["京都市", "京都都"]


def test_japanese_place_variants_skips_names_with_suffix():
    assert japanese_place_variants("横浜市") == []
    assert japanese_place_variants("東京都") == []
    assert japanese_place_variants("大阪府") == []


def test_japanese_place_variants_ignores_non_kanji():
    assert japanese_place_variants("Tokyo") == []
    assert japanese_place_variants("") == []


# ---------------------------------------------------------------------------
# Latin aliases for Taiwan / Hong Kong / Macau
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("name", "country", "expected"),
    [
        ("台北", "TW", "Taipei"),
        ("臺北", "TW", "Taipei"),
        ("高雄", "TW", "Kaohsiung"),
        ("台中", "TW", "Taichung"),
        ("新北", "TW", "New Taipei"),
        ("桃園", "TW", "Taoyuan"),
        ("香港", "HK", "Hong Kong"),
        ("澳門", "MO", "Macau"),
        ("澳门", "MO", "Macau"),
        ("台北市", "TW", "Taipei"),
    ],
)
def test_latin_place_alias(name, country, expected):
    assert latin_place_alias(name, country) == expected


def test_latin_place_alias_unknown():
    assert latin_place_alias("北京", "TW") is None
    assert latin_place_alias("台北", "CN") is None
    assert latin_place_alias("", "TW") is None


# ---------------------------------------------------------------------------
# Kana place prefix
# ---------------------------------------------------------------------------
def test_kana_place_prefix():
    assert kana_place_prefix("とうきょう") == "とうきょう"
    assert kana_place_prefix("さっぽろの天気") == "さっぽろ"
    assert kana_place_prefix("きょうの天気") == "きょう"
    assert kana_place_prefix("Tokyo") == ""


def test_kana_place_prefix_keeps_trailing_conjunction():
    # "きょうと" is Kyoto -- the trailing と belongs to the name.
    assert kana_place_prefix("きょうと") == "きょうと"
    assert romanize_kana(kana_place_prefix("きょうと")) == "kyoto"
