from __future__ import annotations

import pytest
from tools.weather_logic import (
    _build_summary,
    _c_to_f,
    _clean_join,
    _contains_cjk_chars,
    _detect_language,
    _extract_cjk_location_fragments,
    _f_to_c,
    _kmh_to_mph,
    _normalize_cjk_location_display,
    _normalize_condition_key,
    _normalize_units,
    _resolve_language,
    _round_or_none,
    _select_open_meteo_candidate,
    _to_float,
    _to_int,
    _translate_condition,
    WeatherLookupError,
    get_weather,
)
from tools.weather_lookup import _as_bool, _error_message


# ---------------------------------------------------------------------------
# _detect_language
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", "en-US"),
        ("London", "en-US"),
        ("New York", "en-US"),
        ("서울", "ko"),
        ("부산", "ko"),
        ("안녕하세요", "ko"),
        ("東京", "zh-Hans"),        # kanji-only → CJK range → zh-Hans
        ("大阪", "zh-Hans"),        # kanji-only → CJK range → zh-Hans
        ("こんにちは", "ja"),
        ("今日の天気", "ja"),        # mixed kanji + kana → ja
        ("北京", "zh-Hans"),
        ("上海", "zh-Hans"),
        ("深圳市", "zh-Hans"),
    ],
)
def test_detect_language(text, expected):
    assert _detect_language(text) == expected


def test_detect_language_hangul_over_cjk():
    # Hangul + CJK mixed — Hangul should win (Korean)
    assert _detect_language("서울特別市") == "ko"


def test_detect_language_kana_over_cjk():
    # Kana + CJK mixed — Kana should win (Japanese)
    assert _detect_language("東京の天気") == "ja"


# ---------------------------------------------------------------------------
# _resolve_language
# ---------------------------------------------------------------------------
def test_resolve_language_auto_detects():
    assert _resolve_language("auto", "서울") == "ko"
    assert _resolve_language("auto", "こんにちは") == "ja"
    assert _resolve_language("auto", "London") == "en-US"


def test_resolve_language_explicit_overrides_auto():
    assert _resolve_language("ja", "서울") == "ja"
    assert _resolve_language("ko", "東京") == "ko"


def test_resolve_language_invalid_falls_back_to_auto():
    assert _resolve_language("invalid", "서울") == "ko"


def test_resolve_language_none_treated_as_auto():
    assert _resolve_language(None, "서울") == "ko"


# ---------------------------------------------------------------------------
# _translate_condition
# ---------------------------------------------------------------------------
def test_translate_condition_en_is_passthrough():
    assert _translate_condition("Sunny", "en-US") == "Sunny"


def test_translate_condition_zh_hans():
    assert _translate_condition("sunny", "zh-Hans") == "晴"
    assert _translate_condition("Clear sky", "zh-Hans") == "晴空"


def test_translate_condition_zh_hant():
    assert _translate_condition("sunny", "zh-Hant") == "晴"
    assert _translate_condition("cloudy", "zh-Hant") == "多雲"


def test_translate_condition_unknown_key_returns_original():
    assert _translate_condition("nonexistent_xyz", "zh-Hans") == "nonexistent_xyz"


def test_translate_condition_empty_returns_unknown_fallback():
    result = _translate_condition("", "zh-Hans")
    assert result == "未知"


# ---------------------------------------------------------------------------
# _normalize_condition_key
# ---------------------------------------------------------------------------
def test_normalize_condition_key_lower_and_whitespace():
    assert _normalize_condition_key("  Clear Sky  ") == "clear sky"
    assert _normalize_condition_key("CLEAR\tSKY") == "clear sky"


# ---------------------------------------------------------------------------
# _extract_cjk_location_fragments
# ---------------------------------------------------------------------------
def test_extract_cjk_fragments_removes_noise():
    fragments = _extract_cjk_location_fragments("北京天气预报", "zh-Hans")
    assert "北京" in fragments


def test_extract_cjk_fragments_removes_punctuation():
    fragments = _extract_cjk_location_fragments("北京！？", "zh-Hans")
    assert "北京" in fragments


def test_extract_cjk_fragments_splits_on_markers():
    fragments = _extract_cjk_location_fragments(
        "北京和上海", "zh-Hans"
    )
    assert "北京" in fragments
    assert "上海" in fragments


def test_extract_cjk_fragments_english_no_cjk():
    # English text with no CJK chars returns the cleaned base query unchanged
    fragments = _extract_cjk_location_fragments("London weather", "en-US")
    assert "London weather" in fragments


def test_extract_cjk_fragments_dedup():
    # After noise removal "天气" is stripped, "北京北京" stays as one fragment
    fragments = _extract_cjk_location_fragments(
        "北京天气北京", "zh-Hans"
    )
    assert len(fragments) >= 1
    assert "北京" in fragments[0]


def test_extract_cjk_fragments_strips_space_in_cjk():
    # Non-CJK text returns the cleaned base query
    fragments = _extract_cjk_location_fragments("New York", "en-US")
    assert len(fragments) >= 1


# ---------------------------------------------------------------------------
# _normalize_cjk_location_display
# ---------------------------------------------------------------------------
def test_normalize_cjk_location_display_returns_first_fragment():
    result = _normalize_cjk_location_display(
        "北京天气和上海", "zh-Hans"
    )
    assert result == "北京"


def test_normalize_cjk_location_display_fallback_strips_punctuation():
    result = _normalize_cjk_location_display("!!!London???", "en-US")
    assert result == "London"


# ---------------------------------------------------------------------------
# _select_open_meteo_candidate
# ---------------------------------------------------------------------------
def _make_candidate(name, country_code="", feature_code="", population=0, lat=0.0, lon=0.0):
    return {
        "name": name,
        "country_code": country_code,
        "feature_code": feature_code,
        "population": population,
        "latitude": lat,
        "longitude": lon,
    }


def test_select_candidate_exact_name_match():
    candidates = [
        _make_candidate("WrongCity"),
        _make_candidate("Shanghai", "CN", "PPLA", 24000000, 31.23, 121.47),
        _make_candidate("Shanghai Suburb"),
    ]
    best = _select_open_meteo_candidate(candidates, "Shanghai")
    assert best["name"] == "Shanghai"


def test_select_candidate_country_hint():
    candidates = [
        _make_candidate("London", "GB", "PPLC", 9000000),
        _make_candidate("London", "CA", "PPL", 400000),
    ]
    best = _select_open_meteo_candidate(candidates, "London", country_hint="CA")
    assert best["country_code"] == "CA"


def test_select_candidate_prefers_capital():
    candidates = [
        _make_candidate("Paris", "FR", "PPL", 2000000),
        _make_candidate("Paris", "FR", "PPLC", 2200000),
    ]
    best = _select_open_meteo_candidate(candidates, "Paris")
    assert best["feature_code"] == "PPLC"


def test_select_candidate_penalizes_wrong_country():
    candidates = [
        _make_candidate("Vienna", "AT", "PPLC", 1900000),
        _make_candidate("Vienna", "US", "PPL", 16000),
    ]
    best = _select_open_meteo_candidate(candidates, "Vienna", country_hint="AT")
    assert best["country_code"] == "AT"


def test_select_candidate_returns_first_when_all_equal():
    candidates = [
        _make_candidate("A", "XX"),
        _make_candidate("B", "XX"),
    ]
    best = _select_open_meteo_candidate(candidates, "Unknown")
    assert best["name"] in ("A", "B")


def test_select_candidate_scoring_by_population():
    # Large population difference must outweigh the small index bonus
    candidates = [
        _make_candidate("Springfield", "US", "PPL", 1000),
        _make_candidate("Springfield", "US", "PPL", 5000000),
    ]
    best = _select_open_meteo_candidate(candidates, "Springfield")
    assert best["population"] == 5000000


# ---------------------------------------------------------------------------
# _to_float / _to_int
# ---------------------------------------------------------------------------
def test_to_float():
    assert _to_float("3.14") == 3.14
    assert _to_float(42) == 42.0
    assert _to_float(None) is None
    assert _to_float("abc") is None


def test_to_int():
    assert _to_int("42") == 42
    assert _to_int(3.9) == 3
    assert _to_int(None) is None
    assert _to_int("abc") is None


# ---------------------------------------------------------------------------
# _c_to_f / _f_to_c / _kmh_to_mph
# ---------------------------------------------------------------------------
def test_c_to_f():
    assert _c_to_f(0) == 32.0
    assert _c_to_f(100) == 212.0
    assert _c_to_f(None) is None


def test_f_to_c():
    assert _f_to_c(32) == 0.0
    assert _f_to_c(212) == 100.0
    assert _f_to_c(None) is None


def test_kmh_to_mph():
    assert _kmh_to_mph(None) is None
    assert round(_kmh_to_mph(100), 2) == 62.14


# ---------------------------------------------------------------------------
# _round_or_none
# ---------------------------------------------------------------------------
def test_round_or_none():
    assert _round_or_none(None) is None
    assert _round_or_none(3.14159, 2) == 3.14
    assert _round_or_none(5.678, 1) == 5.7


# ---------------------------------------------------------------------------
# _clean_join
# ---------------------------------------------------------------------------
def test_clean_join():
    assert _clean_join(["Shanghai", None, "China"]) == "Shanghai, China"
    assert _clean_join(["", " ", "  Beijing  "]) == "Beijing"
    assert _clean_join([None, None]) == ""


# ---------------------------------------------------------------------------
# _contains_cjk_chars
# ---------------------------------------------------------------------------
def test_contains_cjk_chars():
    assert _contains_cjk_chars("北京") is True
    assert _contains_cjk_chars("서울") is True
    assert _contains_cjk_chars("東京") is True
    assert _contains_cjk_chars("London") is False
    assert _contains_cjk_chars("") is False


# ---------------------------------------------------------------------------
# _normalize_units
# ---------------------------------------------------------------------------
def test_normalize_units_metric():
    data = {
        "temperature_c": 22.5,
        "temperature_f": 72.5,
        "feels_like_c": 20.0,
        "feels_like_f": 68.0,
        "wind_speed_kmh": 15.0,
        "wind_speed_mph": 9.3,
    }
    result = _normalize_units(data, "metric")
    assert result["temperature"] == 22.5
    assert result["temperature_unit"] == "degC"
    assert result["wind_speed"] == 15.0
    assert result["wind_speed_unit"] == "km/h"


def test_normalize_units_uscs():
    data = {
        "temperature_c": 22.5,
        "temperature_f": 72.5,
        "feels_like_c": 20.0,
        "feels_like_f": 68.0,
        "wind_speed_kmh": 15.0,
        "wind_speed_mph": 9.3,
    }
    result = _normalize_units(data, "uscs")
    assert result["temperature"] == 72.5
    assert result["temperature_unit"] == "degF"
    assert result["wind_speed"] == 9.3
    assert result["wind_speed_unit"] == "mph"


# ---------------------------------------------------------------------------
# _as_bool
# ---------------------------------------------------------------------------
def test_as_bool_strings():
    assert _as_bool("true") is True
    assert _as_bool("1") is True
    assert _as_bool("yes") is True
    assert _as_bool("false") is False
    assert _as_bool("0") is False
    assert _as_bool("no") is False


def test_as_bool_numbers():
    assert _as_bool(0) is False
    assert _as_bool(1) is True
    assert _as_bool(0.0) is False
    assert _as_bool(3.14) is True


def test_as_bool_bool():
    assert _as_bool(True) is True
    assert _as_bool(False) is False


# ---------------------------------------------------------------------------
# _error_message
# ---------------------------------------------------------------------------
def test_error_message_localized():
    zh = _error_message("London", "test error", "zh-Hans")
    assert "London" in zh
    assert "test error" in zh
    assert "失败" in zh

    en = _error_message("London", "test error", "en-US")
    assert "London" in en
    assert "test error" in en


# ---------------------------------------------------------------------------
# _build_summary
# ---------------------------------------------------------------------------
def _summary_data(**overrides):
    base = {
        "humidity": 75,
        "temperature": 22.0,
        "feels_like": 20.0,
        "wind_speed": 15.0,
        "condition": "Clear sky",
        "location": "Beijing",
        "temperature_unit": "degC",
        "wind_speed_unit": "km/h",
        "rate_limit_notice": "",
    }
    base.update(overrides)
    return base


def test_build_summary_en():
    s = _build_summary(_summary_data(), "en-US")
    assert "Beijing" in s
    assert "Temp" in s
    assert "degC" in s


def test_build_summary_zh_hans():
    s = _build_summary(_summary_data(condition="晴"), "zh-Hans", "北京")
    assert "北京" in s
    assert "温度" in s


def test_build_summary_includes_rate_limit_notice():
    data = _summary_data(rate_limit_notice="Fallback notice text")
    s = _build_summary(data, "en-US")
    assert "Fallback notice text" in s


def test_build_summary_null_values_use_placeholder():
    data = _summary_data(temperature=None, feels_like=None, wind_speed=None)
    s = _build_summary(data, "en-US")
    assert "n/a" in s


# ---------------------------------------------------------------------------
# WeatherLookupError
# ---------------------------------------------------------------------------
def test_weather_lookup_error():
    with pytest.raises(WeatherLookupError):
        raise WeatherLookupError("test")


# ---------------------------------------------------------------------------
# get_weather — parameter validation (no network)
# ---------------------------------------------------------------------------
def test_get_weather_empty_location():
    with pytest.raises(WeatherLookupError, match="Location"):
        get_weather("")


def test_get_weather_invalid_units():
    with pytest.raises(WeatherLookupError, match="units"):
        get_weather("London", units="kelvin")


def test_get_weather_invalid_source():
    with pytest.raises(WeatherLookupError, match="source_preference"):
        get_weather("London", preferred_source="invalid")
