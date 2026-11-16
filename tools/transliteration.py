"""Romanization helpers for CJK place names.

Open-Meteo's geocoding index only stores some native-script Japanese and Korean
place names, and wttr.in resolves many of them to a same-sounding neighbourhood
instead of the city. Transliterating the query into the Latin form the upstream
indexes actually hold lets the plugin answer those queries with the right city.

Both romanizers are deterministic -- Unicode syllable decomposition for Hangul,
Hepburn for kana -- so no phonetic dictionary ships with the plugin and there is
nothing to maintain. The only lookup table is the administrative divisions of
Taiwan, Hong Kong and Macau.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Hangul -> Revised Romanization
# ---------------------------------------------------------------------------

_HANGUL_BASE = 0xAC00
_HANGUL_SYLLABLE_COUNT = 19 * 21 * 28

_HANGUL_INITIAL = (
    "g",
    "kk",
    "n",
    "d",
    "tt",
    "r",
    "m",
    "b",
    "pp",
    "s",
    "ss",
    "",
    "j",
    "jj",
    "ch",
    "k",
    "t",
    "p",
    "h",
)

_HANGUL_MEDIAL = (
    "a",
    "ae",
    "ya",
    "yae",
    "eo",
    "e",
    "yeo",
    "ye",
    "o",
    "wa",
    "wae",
    "oe",
    "yo",
    "u",
    "wo",
    "we",
    "wi",
    "yu",
    "eu",
    "ui",
    "i",
)

_HANGUL_FINAL = (
    "",
    "k",
    "kk",
    "gs",
    "n",
    "nj",
    "nh",
    "d",
    "l",
    "lg",
    "lm",
    "lb",
    "ls",
    "lt",
    "lp",
    "lh",
    "m",
    "p",
    "bs",
    "s",
    "ss",
    "ng",
    "j",
    "ch",
    "k",
    "t",
    "p",
    "h",
)

# ㄹ is 'r' before these vowels and 'l' everywhere else.
_HANGUL_RIEUL_VOWELS = frozenset("iyuo")


def has_hangul(text: str) -> bool:
    return bool(text) and any(
        _HANGUL_BASE <= ord(ch) < _HANGUL_BASE + _HANGUL_SYLLABLE_COUNT for ch in text
    )


def _hangul_syllable(ch: str) -> tuple[int, int, int] | None:
    code = ord(ch)
    if not (_HANGUL_BASE <= code < _HANGUL_BASE + _HANGUL_SYLLABLE_COUNT):
        return None
    index = code - _HANGUL_BASE
    return index // 588, (index % 588) // 28, index % 28


def _hangul_final_sound(final_index: int) -> str:
    """Romanize a Hangul final consonant."""
    if final_index == 0:
        return ""
    return _HANGUL_FINAL[final_index]


def romanize_hangul(text: str) -> str:
    """Convert Hangul syllables to Revised Romanization.

    Non-Hangul characters are passed through untouched.
    """
    if not text:
        return ""

    parts: list[str] = []
    previous_was_open = True
    for ch in text:
        decomposed = _hangul_syllable(ch)
        if decomposed is None:
            parts.append(ch)
            continue

        initial_index, medial_index, final_index = decomposed

        if initial_index == 5:  # ㄹ
            initial = (
                "r" if _HANGUL_MEDIAL[medial_index] in _HANGUL_RIEUL_VOWELS else "l"
            )
        elif initial_index == 0:  # ㄱ
            initial = "g" if previous_was_open else "k"
        elif initial_index == 7:  # ㅂ
            initial = "b" if previous_was_open else "p"
        else:
            initial = _HANGUL_INITIAL[initial_index]

        # ㅡ before a silent ㅇ is written 'u' (응 -> ung).
        medial = _HANGUL_MEDIAL[medial_index]
        if medial_index == 18 and final_index == 21:
            medial = "u"

        parts.append(initial)
        parts.append(medial)
        parts.append(_hangul_final_sound(final_index))

        previous_was_open = final_index == 0

    return "".join(parts)


# ---------------------------------------------------------------------------
# Kana -> Hepburn
# ---------------------------------------------------------------------------

_KANA_BASE = {
    "あ": "a",
    "い": "i",
    "う": "u",
    "え": "e",
    "お": "o",
    "か": "ka",
    "き": "ki",
    "く": "ku",
    "け": "ke",
    "こ": "ko",
    "が": "ga",
    "ぎ": "gi",
    "ぐ": "gu",
    "げ": "ge",
    "ご": "go",
    "さ": "sa",
    "し": "shi",
    "す": "su",
    "せ": "se",
    "そ": "so",
    "ざ": "za",
    "じ": "ji",
    "ず": "zu",
    "ぜ": "ze",
    "ぞ": "zo",
    "た": "ta",
    "ち": "chi",
    "つ": "tsu",
    "て": "te",
    "と": "to",
    "だ": "da",
    "ぢ": "ji",
    "づ": "zu",
    "で": "de",
    "ど": "do",
    "な": "na",
    "に": "ni",
    "ぬ": "nu",
    "ね": "ne",
    "の": "no",
    "は": "ha",
    "ひ": "hi",
    "ふ": "fu",
    "へ": "he",
    "ほ": "ho",
    "ば": "ba",
    "び": "bi",
    "ぶ": "bu",
    "べ": "be",
    "ぼ": "bo",
    "ぱ": "pa",
    "ぴ": "pi",
    "ぷ": "pu",
    "ぺ": "pe",
    "ぽ": "po",
    "ま": "ma",
    "み": "mi",
    "む": "mu",
    "め": "me",
    "も": "mo",
    "や": "ya",
    "ゆ": "yu",
    "よ": "yo",
    "ら": "ra",
    "り": "ri",
    "る": "ru",
    "れ": "re",
    "ろ": "ro",
    "わ": "wa",
    "ゐ": "wi",
    "ゑ": "we",
    "を": "wo",
    "ん": "n",
    "ゔ": "vu",
    "ぁ": "a",
    "ぃ": "i",
    "ぅ": "u",
    "ぇ": "e",
    "ぉ": "o",
    "ゃ": "ya",
    "ゅ": "yu",
    "ょ": "yo",
    "ゎ": "wa",
}

_KANA_COMBO = {
    "きゃ": "kya",
    "きゅ": "kyu",
    "きょ": "kyo",
    "ぎゃ": "gya",
    "ぎゅ": "gyu",
    "ぎょ": "gyo",
    "しゃ": "sha",
    "しゅ": "shu",
    "しょ": "sho",
    "じゃ": "ja",
    "じゅ": "ju",
    "じょ": "jo",
    "ちゃ": "cha",
    "ちゅ": "chu",
    "ちょ": "cho",
    "にゃ": "nya",
    "にゅ": "nyu",
    "にょ": "nyo",
    "ひゃ": "hya",
    "ひゅ": "hyu",
    "ひょ": "hyo",
    "びゃ": "bya",
    "びゅ": "byu",
    "びょ": "byo",
    "ぴゃ": "pya",
    "ぴゅ": "pyu",
    "ぴょ": "pyo",
    "みゃ": "mya",
    "みゅ": "myu",
    "みょ": "myo",
    "りゃ": "rya",
    "りゅ": "ryu",
    "りょ": "ryo",
    "ふぁ": "fa",
    "ふぃ": "fi",
    "ふぇ": "fe",
    "ふぉ": "fo",
    "うぃ": "wi",
    "うぇ": "we",
    "ゔぁ": "va",
    "ゔぃ": "vi",
    "ゔぇ": "ve",
    "ゔぉ": "vo",
    "てぃ": "ti",
    "でぃ": "di",
    "とぅ": "tu",
    "どぅ": "du",
}

_KATAKANA_START = 0x30A1
_KATAKANA_END = 0x30F6


def _to_hiragana(ch: str) -> str:
    code = ord(ch)
    if _KATAKANA_START <= code <= _KATAKANA_END:
        return chr(code - 0x60)
    return ch


def has_kana(text: str) -> bool:
    return bool(text) and any(0x3041 <= ord(_to_hiragana(ch)) <= 0x309F for ch in text)


# Particles that trail a Japanese place name in a free-form query. "と" and "や"
# are conjunctions rather than trailing particles, and a place name can end in
# them ("きょうと"), so they are left to the query segmentation.
_KANA_PARTICLES = ("から", "まで", "など", "の", "が", "は", "を", "に", "で", "も")


def kana_place_prefix(text: str) -> str:
    """Leading kana run of a query, without a trailing particle.

    A query like "さっぽろの天気" names one place, so only the kana at the front
    is the place name; the rest is grammar.
    """
    prefix = ""
    for ch in text:
        if not has_kana(ch):
            break
        prefix += _to_hiragana(ch)
    for particle in _KANA_PARTICLES:
        prefix = prefix.removesuffix(particle)
    return prefix


def romanize_kana(text: str) -> str:
    """Convert hiragana/katakana to Hepburn romanization.

    Non-kana characters are passed through untouched.
    """
    if not text:
        return ""

    hiragana = "".join(_to_hiragana(ch) for ch in text)
    chunks: list[tuple[str, str]] = []
    index = 0
    while index < len(hiragana):
        pair = hiragana[index : index + 2]
        if pair in _KANA_COMBO:
            chunks.append((pair, _KANA_COMBO[pair]))
            index += 2
            continue
        ch = hiragana[index]
        if ch in ("っ", "ー"):
            chunks.append((ch, ""))
        elif ch in _KANA_BASE:
            chunks.append((ch, _KANA_BASE[ch]))
        else:
            chunks.append((ch, ch))
        index += 1

    # A う after the first mora is a long-vowel marker and is not written out
    # in the Latin forms the upstream indexes use (Tōkyō -> Tokyo).
    filtered: list[tuple[str, str]] = []
    for kana, romaji in chunks:
        if kana == "う" and filtered:
            continue
        filtered.append((kana, romaji))

    # A sokuon doubles the consonant that follows it.
    romaji_parts: list[str] = []
    for position, (kana, romaji) in enumerate(filtered):
        if kana == "っ":
            following = next((r for _, r in filtered[position + 1 :] if r), "")
            if following:
                romaji_parts.append(following[0])
            continue
        romaji_parts.append(romaji)

    # A doubled vowel is written as a single letter (Ōsaka -> Osaka).
    return re.sub(r"([aeiou])\1", r"\1", "".join(romaji_parts))


# ---------------------------------------------------------------------------
# Japanese place-name variants
# ---------------------------------------------------------------------------

# The upstream index stores most Japanese municipalities with an administrative
# suffix ("横浜市"), but not all of them ("仙台", "長野"), and a bare name can
# also match an unrelated hamlet in another prefecture.
_JAPANESE_SUFFIXES = ("市", "都")
_JAPANESE_SUFFIX_CHARS = frozenset("市府県区町村道国")


def has_kanji(text: str) -> bool:
    return bool(text) and any(
        0x4E00 <= ord(ch) <= 0x9FFF or 0xF900 <= ord(ch) <= 0xFAFF for ch in text
    )


# Korean cities and counties carry an administrative suffix ("수원시") that the
# Latin names the upstream index uses drop ("Suwon").
_KOREAN_ADMIN_SUFFIXES = ("시", "군", "도")


def strip_korean_admin_suffix(text: str) -> str:
    """Drop a trailing Korean administrative suffix from a place name."""
    if len(text) >= 3 and text[-1] in _KOREAN_ADMIN_SUFFIXES:
        return text[:-1]
    return text


def japanese_place_variants(name: str) -> list[str]:
    """Return administrative-suffix variants of a Japanese place name."""
    name = (name or "").strip()
    if not name or not has_kanji(name):
        return []
    if name[-1] in _JAPANESE_SUFFIX_CHARS:
        return []
    # "東京都" already carries the suffix, but "京都" is a city name that happens
    # to end in the same character.
    if name[-1] == "都" and len(name) > 2:
        return []
    return [f"{name}{suffix}" for suffix in _JAPANESE_SUFFIXES]


# Taiwan, Hong Kong and Macau are indexed under their Latin names upstream; the
# Chinese names are only partly present. This list is the set of administrative
# divisions of those regions, which changes very rarely.
_LATIN_PLACE_ALIASES: dict[str, dict[str, str]] = {
    "TW": {
        "台湾": "Taiwan",
        "台灣": "Taiwan",
        "臺灣": "Taiwan",
        "台北": "Taipei",
        "臺北": "Taipei",
        "高雄": "Kaohsiung",
        "台中": "Taichung",
        "臺中": "Taichung",
        "新北": "New Taipei",
        "桃园": "Taoyuan",
        "桃園": "Taoyuan",
        "基隆": "Keelung",
        "新竹": "Hsinchu",
        "嘉义": "Chiayi",
        "嘉義": "Chiayi",
        "宜兰": "Yilan",
        "宜蘭": "Yilan",
        "花莲": "Hualien",
        "花蓮": "Hualien",
        "台东": "Taitung",
        "臺東": "Taitung",
        "台南": "Tainan",
        "臺南": "Tainan",
        "屏东": "Pingtung",
        "屏東": "Pingtung",
        "澎湖": "Penghu",
        "苗栗": "Miaoli",
        "彰化": "Changhua",
        "南投": "Nantou",
        "雲林": "Yunlin",
        "云林": "Yunlin",
        "金門": "Kinmen",
        "金门": "Kinmen",
        "連江": "Lienchiang",
        "连江": "Lienchiang",
    },
    "HK": {
        "香港": "Hong Kong",
        "香港島": "Hong Kong Island",
        "香港岛": "Hong Kong Island",
        "港島": "Hong Kong Island",
        "港岛": "Hong Kong Island",
        "九龍": "Kowloon",
        "九龙": "Kowloon",
        "九龍城": "Kowloon City",
        "九龙城": "Kowloon City",
        "新界": "New Territories",
        "大嶼山": "Lantau Island",
        "大屿山": "Lantau Island",
        "銅鑼灣": "Causeway Bay",
        "铜锣湾": "Causeway Bay",
        "尖沙咀": "Tsim Sha Tsui",
        "旺角": "Mong Kok",
        "荃灣": "Tsuen Wan",
        "荃湾": "Tsuen Wan",
        "屯門": "Tuen Mun",
        "屯门": "Tuen Mun",
        "元朗": "Yuen Long",
        "沙田": "Sha Tin",
        "將軍澳": "Tseung Kwan O",
        "将军澳": "Tseung Kwan O",
        "東涌": "Tung Chung",
        "东涌": "Tung Chung",
    },
    "MO": {
        "澳门": "Macau",
        "澳門": "Macau",
        "澳門半島": "Macau Peninsula",
        "澳门半岛": "Macau Peninsula",
        "氹仔": "Taipa",
        "路環": "Coloane",
        "路环": "Coloane",
        "路氹城": "Cotai",
        "媽閣": "Barra",
        "妈阁": "Barra",
    },
}

_PLACE_ALIAS_SUFFIXES = ("市", "縣", "县", "省", "區", "区", "特別市", "特别市")


def latin_place_alias(name: str, country_code: str) -> str | None:
    """Latin name of a place the upstream index only stores under its English name."""
    aliases = _LATIN_PLACE_ALIASES.get(country_code)
    if not aliases:
        return None
    name = (name or "").strip()
    alias = aliases.get(name)
    if alias:
        return alias
    for suffix in _PLACE_ALIAS_SUFFIXES:
        if name.endswith(suffix):
            return aliases.get(name[: -len(suffix)])
    return None


def country_place_names(country_code: str) -> tuple[str, ...]:
    """Return native-script place names known for a country or region."""
    return tuple(_LATIN_PLACE_ALIASES.get(country_code.upper(), {}))
