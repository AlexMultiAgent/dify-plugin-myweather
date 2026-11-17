from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock, patch

import pytest
import requests
import yaml

from tools.weather_logic import (
    DEFAULT_TIMEOUT,
    MAX_LOCATION_CANDIDATES,
    WeatherLookupError,
    WeatherLookupTimeout,
    _build_summary,
    _c_to_f,
    _candidate_locations,
    _clean_join,
    _contains_cjk_chars,
    _detect_language,
    _extract_cjk_location_fragments,
    _f_to_c,
    _fetch_from_open_meteo,
    _fetch_from_wttr,
    _infer_country_hints,
    _kmh_to_mph,
    _normalize_cjk_location_display,
    _normalize_condition_key,
    _normalize_units,
    _open_meteo_queries,
    _resolve_language,
    _retry_request,
    _round_or_none,
    _select_open_meteo_candidate,
    _to_float,
    _to_int,
    _translate_condition,
    get_weather,
)
from tools.weather_lookup import (
    _OUTPUT_FIELDS,
    WeatherLookupTool,
    _as_bool,
    _error_message,
)


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
        ("東京", "zh-Hans"),  # kanji-only → CJK range → zh-Hans
        ("大阪", "zh-Hans"),  # kanji-only → CJK range → zh-Hans
        ("こんにちは", "ja"),
        ("今日の天気", "ja"),  # mixed kanji + kana → ja
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
    fragments = _extract_cjk_location_fragments("北京和上海", "zh-Hans")
    assert "北京" in fragments
    assert "上海" in fragments


def test_extract_cjk_fragments_english_no_cjk():
    # English text with no CJK chars returns the cleaned base query unchanged
    fragments = _extract_cjk_location_fragments("London weather", "en-US")
    assert "London weather" in fragments


def test_extract_cjk_fragments_dedup():
    # After noise removal "天气" is stripped, "北京北京" stays as one fragment
    fragments = _extract_cjk_location_fragments("北京天气北京", "zh-Hans")
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
    result = _normalize_cjk_location_display("北京天气和上海", "zh-Hans")
    assert result == "北京"


def test_normalize_cjk_location_display_fallback_strips_punctuation():
    result = _normalize_cjk_location_display("!!!London???", "en-US")
    assert result == "London"


# ---------------------------------------------------------------------------
# _select_open_meteo_candidate
# ---------------------------------------------------------------------------
def _make_candidate(
    name, country_code="", feature_code="", population=0, lat=0.0, lon=0.0
):
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
    assert _to_int(3.9) == 4
    assert _to_int(3.2) == 3
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
    converted = _kmh_to_mph(100)
    assert converted is not None
    assert round(converted, 2) == 62.14


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
    assert result["temperature_unit"] == "°C"
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
    assert result["temperature_unit"] == "°F"
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
    assert _as_bool("off") is False
    assert _as_bool("disabled") is False
    assert _as_bool("n") is False
    assert _as_bool("random_string") is False


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
        "temperature_unit": "°C",
        "wind_speed_unit": "km/h",
        "rate_limit_notice": "",
    }
    base.update(overrides)
    return base


def test_build_summary_en():
    s = _build_summary(_summary_data(), "en-US")
    assert "Beijing" in s
    assert "Temp" in s
    assert "°C" in s


def test_build_summary_zh_hans():
    s = _build_summary(_summary_data(condition="晴"), "zh-Hans", "北京")
    assert "温度" in s
    # The provider's resolved place wins over the raw query, otherwise a source
    # that matched the wrong city would be hidden behind the user's wording.
    assert "Beijing" in s


def test_build_summary_falls_back_to_query_without_resolved_location():
    s = _build_summary(_summary_data(location=""), "zh-Hans", "北京")
    assert "北京" in s


def test_build_summary_includes_rate_limit_notice():
    data = _summary_data(rate_limit_notice="Fallback notice text")
    s = _build_summary(data, "en-US")
    assert "Fallback notice text" in s


def test_build_summary_null_values_use_placeholder():
    data = _summary_data(temperature=None, feels_like=None, wind_speed=None)
    s = _build_summary(data, "en-US")
    assert "n/a" in s


# ---------------------------------------------------------------------------
# _candidate_locations — word-boundary noise removal
# ---------------------------------------------------------------------------
def test_candidate_locations_does_not_corrupt_short_token_names():
    # "now" must not match inside "Snowville", "in" must not match inside "Beijing"
    candidates = _candidate_locations("Snowville weather now")
    assert any("Snowville" in c for c in candidates)

    candidates = _candidate_locations("Beijing weather today")
    assert any("Beijing" in c for c in candidates)

    candidates = _candidate_locations("Atlanta forecast")
    assert any("Atlanta" in c for c in candidates)


def test_candidate_locations_removes_standalone_noise_words():
    candidates = _candidate_locations("weather in London today")
    assert any("London" in c for c in candidates)


# ---------------------------------------------------------------------------
# _select_open_meteo_candidate — defensive empty check
# ---------------------------------------------------------------------------
def test_select_candidate_empty_list_raises():
    with pytest.raises(ValueError, match="empty"):
        _select_open_meteo_candidate([], "Tokyo")


# ---------------------------------------------------------------------------
# _resolve_language — kanji + country hint disambiguation
# ---------------------------------------------------------------------------
def test_resolve_language_kanji_with_jp_hint():
    # Pure kanji (no kana) is ambiguous, but JP country hint disambiguates
    assert _resolve_language("auto", "東京") == "ja"


def test_resolve_language_kanji_with_kr_hint():
    # Pure CJK with KR hint should resolve to Korean
    assert _resolve_language("auto", "서울") == "ko"


def test_resolve_language_kanji_without_hint_defaults_zh_hans():
    # "北京" has CN hint implicitly, but no JP/KR hint, so stays zh-Hans
    assert _resolve_language("auto", "北京") == "zh-Hans"


def test_resolve_language_tw_hint_returns_zh_hant():
    # CJK text with Taiwan country hint → zh-Hant
    assert _resolve_language("auto", "台北") == "zh-Hant"
    assert _resolve_language("auto", "臺灣") == "zh-Hant"


def test_resolve_language_hk_hint_returns_zh_hant():
    assert _resolve_language("auto", "香港") == "zh-Hant"


def test_resolve_language_mo_hint_returns_zh_hant():
    assert _resolve_language("auto", "澳门") == "zh-Hant"


def test_resolve_language_english_tw_hk_mo_text_returns_en():
    # Latin text like "Taipei" has no CJK chars → en-US, country hints never checked
    assert _resolve_language("auto", "Taipei") == "en-US"
    assert _resolve_language("auto", "Hong Kong") == "en-US"
    assert _resolve_language("auto", "Macau") == "en-US"


def test_resolve_language_explicit_overrides_zh_hant_hint():
    assert _resolve_language("ja", "台北") == "ja"
    assert _resolve_language("en-US", "香港") == "en-US"


@pytest.mark.parametrize(
    ("place", "expected_language", "expected_hint"),
    [
        ("九龍", "zh-Hant", "HK"),
        ("嘉义", "zh-Hant", "TW"),
        ("岐阜", "ja", "JP"),
        ("別府", "ja", "JP"),
    ],
)
def test_resolve_language_for_supported_han_places(
    place, expected_language, expected_hint
):
    assert _infer_country_hints(place) == [expected_hint]
    assert _resolve_language("auto", place) == expected_language


def test_country_hints_do_not_match_latin_substrings():
    assert _infer_country_hints("Chinatown, San Francisco") == []
    assert _infer_country_hints("Koreatown, Los Angeles") == []
    assert _infer_country_hints("China Lake") == []


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


def test_get_weather_rejects_excessive_location_length():
    with pytest.raises(WeatherLookupError, match="too long"):
        get_weather("L" * 201, session=Mock(spec=requests.Session))


def test_get_weather_invalid_units():
    with pytest.raises(WeatherLookupError, match="units"):
        get_weather("London", units="kelvin")


def test_get_weather_invalid_source():
    with pytest.raises(WeatherLookupError, match="source_preference"):
        get_weather("London", preferred_source="invalid")


# ---------------------------------------------------------------------------
# Mock fixtures for upstream API responses
# ---------------------------------------------------------------------------


def _mock_wttr_response(
    location="London",
    country="Test Country",
    temp_c="22.0",
    temp_f="72.0",
    feels_c="20.0",
    feels_f="68.0",
    humidity="75",
    wind_kmh="15.0",
    condition="Clear",
):
    return {
        "current_condition": [
            {
                "temp_C": temp_c,
                "temp_F": temp_f,
                "FeelsLikeC": feels_c,
                "FeelsLikeF": feels_f,
                "humidity": humidity,
                "windspeedKmph": wind_kmh,
                "weatherDesc": [{"value": condition}],
            }
        ],
        "nearest_area": [
            {
                "areaName": [{"value": location}],
                "region": [{"value": "Test Region"}],
                "country": [{"value": country}],
            }
        ],
    }


def _mock_open_meteo_geocode_response(
    name="London",
    country_code="GB",
    feature_code="PPLC",
    population=9000000,
    lat=51.5,
    lon=-0.1,
):
    return {
        "results": [
            {
                "name": name,
                "country_code": country_code,
                "feature_code": feature_code,
                "population": population,
                "latitude": lat,
                "longitude": lon,
                "admin1": "Test Admin",
                "country": "Test Country",
            }
        ],
    }


def _mock_open_meteo_forecast_response(
    temp_c=15.5, feels_c=14.0, humidity=68, wind_kmh=12.3, weather_code=1
):
    return {
        "current": {
            "temperature_2m": temp_c,
            "apparent_temperature": feels_c,
            "relative_humidity_2m": humidity,
            "wind_speed_10m": wind_kmh,
            "weather_code": weather_code,
        },
    }


# ---------------------------------------------------------------------------
# _retry_request
# ---------------------------------------------------------------------------


def test_retry_request_succeeds_first_attempt():
    session = Mock(spec=requests.Session)
    mock_response = Mock(spec=requests.Response)
    mock_response.raise_for_status.return_value = None
    session.request.return_value = mock_response

    result = _retry_request("GET", "http://example.com", session)
    assert result is mock_response
    assert session.request.call_count == 1


def test_retry_request_retries_on_connection_error():
    session = Mock(spec=requests.Session)
    mock_response = Mock(spec=requests.Response)
    mock_response.raise_for_status.return_value = None
    session.request.side_effect = [
        requests.ConnectionError("fail"),
        requests.ConnectionError("fail"),
        mock_response,
    ]

    result = _retry_request("GET", "http://example.com", session)
    assert result is mock_response
    assert session.request.call_count == 3


def test_retry_request_raises_after_max_retries():
    session = Mock(spec=requests.Session)
    session.request.side_effect = requests.ConnectionError("fail")

    with pytest.raises(requests.ConnectionError):
        _retry_request("GET", "http://example.com", session)
    assert session.request.call_count == 3  # 1 initial + 2 retries


def test_retry_request_does_not_retry_http_error():
    session = Mock(spec=requests.Session)
    mock_response = Mock(spec=requests.Response)
    mock_response.raise_for_status.side_effect = requests.HTTPError("400")
    session.request.return_value = mock_response

    with pytest.raises(requests.HTTPError):
        _retry_request("GET", "http://example.com", session)
    assert session.request.call_count == 1


def test_retry_request_rejects_redirects():
    session = Mock(spec=requests.Session)
    mock_response = Mock(spec=requests.Response)
    mock_response.status_code = 302
    mock_response.raise_for_status.return_value = None
    session.request.return_value = mock_response

    with pytest.raises(requests.HTTPError, match="redirect"):
        _retry_request("GET", "https://example.com", session)

    assert session.request.call_args.kwargs["allow_redirects"] is False


def test_retry_debug_logging_does_not_include_transport_error_url(caplog, monkeypatch):
    session = Mock(spec=requests.Session)
    session.request.side_effect = requests.ConnectionError(
        "failed https://wttr.in/Sensitive+Place+Name"
    )
    monkeypatch.setattr("tools.weather_logic.time.sleep", lambda _delay: None)

    with (
        caplog.at_level(logging.DEBUG, logger="tools.weather_logic"),
        pytest.raises(requests.ConnectionError),
    ):
        _retry_request("GET", "https://wttr.in/Sensitive+Place+Name", session)

    assert "Sensitive+Place" not in caplog.text


def test_retry_request_retries_on_429():
    session = Mock(spec=requests.Session)
    error_resp = Mock(spec=requests.Response)
    error_resp.status_code = 429
    success_resp = Mock(spec=requests.Response)
    success_resp.raise_for_status.return_value = None
    session.request.side_effect = [
        requests.HTTPError("429", response=error_resp),
        success_resp,
    ]
    result = _retry_request("GET", "http://example.com", session)
    assert result is success_resp
    assert session.request.call_count == 2


def test_retry_request_retries_on_503():
    session = Mock(spec=requests.Session)
    error_resp = Mock(spec=requests.Response)
    error_resp.status_code = 503
    success_resp = Mock(spec=requests.Response)
    success_resp.raise_for_status.return_value = None
    session.request.side_effect = [
        requests.HTTPError("503", response=error_resp),
        success_resp,
    ]
    result = _retry_request("GET", "http://example.com", session)
    assert result is success_resp
    assert session.request.call_count == 2


def test_retry_request_raises_after_max_429_retries():
    session = Mock(spec=requests.Session)
    error_resp = Mock(spec=requests.Response)
    error_resp.status_code = 429
    session.request.side_effect = requests.HTTPError("429", response=error_resp)
    with pytest.raises(requests.HTTPError):
        _retry_request("GET", "http://example.com", session)
    assert session.request.call_count == 3


def test_retry_request_clamps_timeout_to_lookup_deadline(monkeypatch):
    session = Mock(spec=requests.Session)
    mock_response = Mock(spec=requests.Response)
    mock_response.raise_for_status.return_value = None
    session.request.return_value = mock_response
    monkeypatch.setattr("tools.weather_logic.time.monotonic", lambda: 995.0)

    _retry_request(
        "GET",
        "http://example.com",
        session,
        timeout=DEFAULT_TIMEOUT,
        deadline=1000.0,
    )

    assert session.request.call_args.kwargs["timeout"] == pytest.approx(5.0)


def test_retry_request_stops_when_backoff_would_exceed_deadline(monkeypatch):
    session = Mock(spec=requests.Session)
    session.request.side_effect = requests.ConnectionError("fail")
    monkeypatch.setattr("tools.weather_logic.time.monotonic", lambda: 999.5)

    with pytest.raises(WeatherLookupTimeout, match="deadline"):
        _retry_request(
            "GET",
            "http://example.com",
            session,
            timeout=DEFAULT_TIMEOUT,
            deadline=1000.0,
        )

    assert session.request.call_count == 1


# ---------------------------------------------------------------------------
# _fetch_from_wttr (mocked)
# ---------------------------------------------------------------------------


def test_fetch_from_wttr_parses_response():
    session = Mock(spec=requests.Session)
    mock_resp = Mock(spec=requests.Response)
    mock_resp.json.return_value = _mock_wttr_response(
        location="London",
        temp_c="22.0",
        temp_f="72.0",
        humidity="75",
        wind_kmh="15.0",
        condition="Clear",
    )
    mock_resp.raise_for_status.return_value = None
    session.request.return_value = mock_resp

    result = _fetch_from_wttr("London", session)
    assert result["source"] == "wttr"
    assert result["temperature_c"] == 22.0
    assert result["temperature_f"] == 72.0
    assert result["humidity"] == 75
    assert result["wind_speed_kmh"] == 15.0
    assert result["condition"] == "Clear"
    assert result["location"] == "London, Test Region, Test Country"


def test_fetch_from_wttr_rejects_cross_region_match_for_han_query():
    session = Mock(spec=requests.Session)
    mock_resp = Mock(spec=requests.Response)
    mock_resp.json.return_value = _mock_wttr_response(
        location="Ma Tso Lung", country="Hong Kong SAR"
    )
    mock_resp.raise_for_status.return_value = None
    session.request.return_value = mock_resp

    with pytest.raises(WeatherLookupError, match="matched Hong Kong"):
        _fetch_from_wttr("深圳", session)


def test_fetch_from_wttr_accepts_expected_macau_region():
    session = Mock(spec=requests.Session)
    mock_resp = Mock(spec=requests.Response)
    mock_resp.json.return_value = _mock_wttr_response(
        location="Macau", country="Macau SAR, China"
    )
    mock_resp.raise_for_status.return_value = None
    session.request.return_value = mock_resp

    result = _fetch_from_wttr("澳门", session)

    assert result["location"].startswith("Macau")


def test_fetch_from_wttr_rejects_empty_weather_payload():
    session = Mock(spec=requests.Session)
    mock_resp = Mock(spec=requests.Response)
    mock_resp.json.return_value = {"current_condition": [], "nearest_area": []}
    mock_resp.raise_for_status.return_value = None
    session.request.return_value = mock_resp

    with pytest.raises(WeatherLookupError, match="temperature"):
        _fetch_from_wttr("Nowhere", session)


# ---------------------------------------------------------------------------
# _fetch_from_open_meteo (mocked)
# ---------------------------------------------------------------------------


def test_fetch_from_open_meteo_parses_response():
    session = Mock(spec=requests.Session)
    geo_resp = Mock(spec=requests.Response)
    geo_resp.json.return_value = _mock_open_meteo_geocode_response("London", "GB")
    geo_resp.raise_for_status.return_value = None

    forecast_resp = Mock(spec=requests.Response)
    forecast_resp.json.return_value = _mock_open_meteo_forecast_response(
        temp_c=15.5,
        feels_c=14.0,
        humidity=68,
        wind_kmh=12.3,
        weather_code=1,
    )
    forecast_resp.raise_for_status.return_value = None

    session.request.side_effect = [geo_resp, forecast_resp]

    result = _fetch_from_open_meteo("London", session, language="en-US")
    assert result["source"] == "open-meteo"
    assert result["temperature_c"] == 15.5
    assert result["temperature_f"] == _c_to_f(15.5)
    assert result["feels_like_c"] == 14.0
    assert result["humidity"] == 68
    assert result["wind_speed_kmh"] == 12.3
    assert result["condition"] == "Mainly clear"


def test_fetch_from_open_meteo_rejects_empty_current_payload():
    session = Mock(spec=requests.Session)
    geo_resp = Mock(spec=requests.Response)
    geo_resp.json.return_value = _mock_open_meteo_geocode_response("London", "GB")
    geo_resp.raise_for_status.return_value = None

    forecast_resp = Mock(spec=requests.Response)
    forecast_resp.json.return_value = {"current": {}}
    forecast_resp.raise_for_status.return_value = None

    session.request.side_effect = [geo_resp, forecast_resp]

    with pytest.raises(WeatherLookupError, match="temperature"):
        _fetch_from_open_meteo("London", session, language="en-US")


# ---------------------------------------------------------------------------
# get_weather — mocked network calls (full integration)
# ---------------------------------------------------------------------------


def _build_mock_session(
    wttr_data=None,
    geocode_data=None,
    forecast_data=None,
    geocode_side_effect=None,
    forecast_side_effect=None,
):
    """Build a mock session that returns canned wttr / open-meteo responses."""
    session = Mock(spec=requests.Session)

    def _make_resp(json_body):
        resp = Mock(spec=requests.Response)
        resp.json.return_value = json_body
        resp.raise_for_status.return_value = None
        return resp

    def request_side_effect(method, url, **kwargs):
        if "wttr.in" in url:
            return _make_resp(wttr_data or _mock_wttr_response())
        if "geocoding" in url:
            if callable(geocode_side_effect):
                return geocode_side_effect()
            return _make_resp(geocode_data or _mock_open_meteo_geocode_response())
        if "forecast" in url:
            if callable(forecast_side_effect):
                return forecast_side_effect()
            return _make_resp(forecast_data or _mock_open_meteo_forecast_response())
        raise ValueError(f"Unexpected URL: {url}")

    session.request.side_effect = request_side_effect
    return session


def test_get_weather_wttr_primary_succeeds():
    session = _build_mock_session()
    result = get_weather(
        "London",
        units="metric",
        preferred_source="wttr",
        language="en-US",
        session=session,
    )
    assert result["source"] == "wttr"
    assert result["temperature"] == 22.0
    assert result["temperature_unit"] == "°C"
    assert result["language"] == "en-US"
    assert result["condition"] == "Clear"
    assert result["summary"] != ""
    assert result["open_meteo_compliance_notice"] == ""
    assert result["rate_limit_notice"] == ""


def test_get_weather_open_meteo_primary_succeeds():
    session = _build_mock_session()
    result = get_weather(
        "London",
        units="metric",
        preferred_source="open-meteo",
        language="en-US",
        session=session,
    )
    assert result["source"] == "open-meteo"
    assert result["open_meteo_compliance_notice"] != ""
    assert result["temperature"] == 15.5


def test_get_weather_uscs_units():
    session = _build_mock_session()
    result = get_weather(
        "London",
        units="uscs",
        preferred_source="wttr",
        language="en-US",
        session=session,
    )
    assert result["temperature_unit"] == "°F"
    assert result["wind_speed_unit"] == "mph"
    assert result["temperature"] == 72.0


def test_get_weather_fallback_wttr_fails_open_meteo_succeeds():
    """When wttr is primary but fails, fallback to Open-Meteo should succeed."""
    session = Mock(spec=requests.Session)

    def make_resp(body):
        resp = Mock(spec=requests.Response)
        resp.json.return_value = body
        resp.raise_for_status.return_value = None
        return resp

    # wttr.in fails, Open-Meteo geocoding + forecast succeed
    def side_effect(method, url, **kwargs):
        if "wttr.in" in url:
            raise requests.ConnectionError("wttr down")
        if "geocoding" in url:
            return make_resp(_mock_open_meteo_geocode_response())
        if "forecast" in url:
            return make_resp(_mock_open_meteo_forecast_response())
        raise ValueError(f"Unexpected URL: {url}")

    session.request.side_effect = side_effect

    result = get_weather(
        "London", preferred_source="wttr", language="en-US", session=session
    )
    assert result["source"] == "open-meteo"


def test_get_weather_open_meteo_fallback_with_rate_limit_notice():
    """When Open-Meteo is primary and fails with 429, fallback to wttr.in with rate_limit_notice."""
    session = Mock(spec=requests.Session)

    # Open-Meteo geocoding raises HTTP 429
    geo_resp = Mock(spec=requests.Response)
    geo_resp.status_code = 429
    http_error = requests.HTTPError("429 Too Many Requests")
    http_error.response = geo_resp
    geo_resp.raise_for_status.side_effect = http_error

    # wttr.in succeeds
    wttr_resp = Mock(spec=requests.Response)
    wttr_resp.json.return_value = _mock_wttr_response()
    wttr_resp.raise_for_status.return_value = None

    def side_effect(method, url, **kwargs):
        if "open-meteo" in url or "geocoding" in url:
            return geo_resp
        return wttr_resp

    session.request.side_effect = side_effect

    result = get_weather(
        "London", preferred_source="open-meteo", language="en-US", session=session
    )
    assert result["source"] == "wttr"
    assert "rate limited" in result["rate_limit_notice"].lower()
    assert "wttr.in" in result["rate_limit_notice"]


def test_get_weather_all_sources_fail():
    session = Mock(spec=requests.Session)
    session.request.side_effect = requests.ConnectionError("network down")

    with pytest.raises(WeatherLookupError, match="All weather sources failed"):
        get_weather("London", session=session)


def test_get_weather_limits_candidate_fanout(monkeypatch):
    attempted: list[str] = []

    def fail_open_meteo(open_meteo_query, *_args, **_kwargs):
        attempted.append(open_meteo_query)
        raise WeatherLookupError("no match")

    def fail_wttr(*_args, **_kwargs):
        raise WeatherLookupError("no match")

    monkeypatch.setattr("tools.weather_logic._fetch_from_open_meteo", fail_open_meteo)
    monkeypatch.setattr("tools.weather_logic._fetch_from_wttr", fail_wttr)

    with pytest.raises(WeatherLookupError, match="All weather sources failed"):
        get_weather("a和b和c和d和e和f", preferred_source="open-meteo")

    assert len(attempted) == MAX_LOCATION_CANDIDATES


def test_get_weather_does_not_start_fallback_after_deadline(monkeypatch):
    calls: list[str] = []

    def timeout(*_args, **_kwargs):
        calls.append("open-meteo")
        raise WeatherLookupTimeout("Weather lookup deadline exceeded.")

    def fallback(*_args, **_kwargs):
        calls.append("wttr")
        return {"source": "wttr"}

    monkeypatch.setattr("tools.weather_logic._fetch_from_open_meteo", timeout)
    monkeypatch.setattr("tools.weather_logic._fetch_from_wttr", fallback)

    with pytest.raises(WeatherLookupError, match="deadline"):
        get_weather("London", preferred_source="open-meteo")

    assert calls == ["open-meteo"]


def test_get_weather_stops_open_meteo_after_network_failure(monkeypatch):
    open_meteo_calls: list[str] = []

    def timeout(candidate, *_args, **_kwargs):
        open_meteo_calls.append(candidate)
        raise requests.ReadTimeout("provider timed out")

    def fail_wttr(*_args, **_kwargs):
        raise WeatherLookupError("wttr unavailable")

    monkeypatch.setattr("tools.weather_logic._fetch_from_open_meteo", timeout)
    monkeypatch.setattr("tools.weather_logic._fetch_from_wttr", fail_wttr)

    with pytest.raises(WeatherLookupError, match="All weather sources failed"):
        get_weather(
            "a和b和c和d和e和f",
            preferred_source="open-meteo",
            language="zh-Hans",
        )

    assert len(open_meteo_calls) == 1


def test_get_weather_propagates_language_to_output():
    session = _build_mock_session()
    result = get_weather(
        "서울",
        units="metric",
        preferred_source="wttr",
        language="auto",
        session=session,
    )
    assert result["language"] == "ko"


def test_get_weather_explicit_language_overrides_auto():
    session = _build_mock_session()
    result = get_weather(
        "서울",
        units="metric",
        preferred_source="wttr",
        language="en-US",
        session=session,
    )
    assert result["language"] == "en-US"


def test_get_weather_includes_raw_payload():
    session = _build_mock_session()
    result = get_weather("London", preferred_source="wttr", session=session)
    assert "raw" in result
    assert "current_condition" in result["raw"]


# ---------------------------------------------------------------------------
# Source fallback — Open-Meteo geocoding without a match
# ---------------------------------------------------------------------------
def test_get_weather_open_meteo_no_match_falls_back_to_wttr():
    session = _build_mock_session(geocode_data={"results": []})
    result = get_weather(
        "London", language="en-US", preferred_source="open-meteo", session=session
    )
    assert result["source"] == "wttr"
    assert result["rate_limit_notice"]
    assert result["temperature"] == 22.0


def test_get_weather_japanese_no_match_does_not_query_wttr():
    session = Mock(spec=requests.Session)

    def side_effect(method, url, **kwargs):
        if "wttr.in" in url:
            raise AssertionError("wttr.in must not be queried for Japanese input")
        resp = Mock(spec=requests.Response)
        resp.json.return_value = {"results": []}
        resp.raise_for_status.return_value = None
        return resp

    session.request.side_effect = side_effect
    with pytest.raises(WeatherLookupError, match="All weather sources failed"):
        get_weather(
            "東京", language="ja", preferred_source="open-meteo", session=session
        )


def test_formatting_error_is_not_reported_as_source_failure():
    """A bug in this plugin's formatting must not be blamed on the upstream provider."""
    session = _build_mock_session()
    with (
        patch("tools.weather_logic._build_summary", side_effect=TypeError("boom")),
        pytest.raises(WeatherLookupError, match="Failed to format"),
    ):
        get_weather("London", session=session)


def test_fetch_from_wttr_strips_condition_whitespace():
    session = Mock(spec=requests.Session)
    mock_resp = Mock(spec=requests.Response)
    mock_resp.json.return_value = _mock_wttr_response(condition="Partly Cloudy ")
    mock_resp.raise_for_status.return_value = None
    session.request.return_value = mock_resp

    result = _fetch_from_wttr("London", session)
    assert result["condition"] == "Partly Cloudy"


def test_fetch_logging_does_not_include_raw_query(caplog):
    session = Mock(spec=requests.Session)
    mock_resp = Mock(spec=requests.Response)
    mock_resp.json.return_value = _mock_wttr_response()
    mock_resp.raise_for_status.return_value = None
    session.request.return_value = mock_resp

    with caplog.at_level(logging.INFO):
        _fetch_from_wttr("Sensitive Place Name", session)

    assert "Sensitive Place Name" not in caplog.text


def test_failure_debug_logging_does_not_include_raw_query(caplog):
    session = Mock(spec=requests.Session)
    session.request.side_effect = requests.HTTPError(
        "400 for https://wttr.in/Sensitive+Place+Name"
    )

    with (
        caplog.at_level(logging.DEBUG, logger="tools.weather_logic"),
        pytest.raises(WeatherLookupError, match="All weather sources failed"),
    ):
        get_weather(
            "Sensitive Place Name",
            preferred_source="wttr",
            language="en-US",
            session=session,
        )

    assert "Sensitive Place Name" not in caplog.text
    assert "Sensitive%20Place" not in caplog.text
    assert "Sensitive+Place" not in caplog.text


def test_get_weather_wttr_malformed_payload_falls_back_to_open_meteo():
    session = Mock(spec=requests.Session)

    def response(body):
        resp = Mock(spec=requests.Response)
        resp.json.return_value = body
        resp.raise_for_status.return_value = None
        return resp

    session.request.side_effect = [
        response({"current_condition": ["bad"]}),
        response(_mock_open_meteo_geocode_response()),
        response(_mock_open_meteo_forecast_response()),
    ]

    result = get_weather("London", preferred_source="wttr", session=session)
    assert result["source"] == "open-meteo"


def test_get_weather_open_meteo_malformed_payload_falls_back_to_wttr():
    session = Mock(spec=requests.Session)

    def response(body):
        resp = Mock(spec=requests.Response)
        resp.json.return_value = body
        resp.raise_for_status.return_value = None
        return resp

    session.request.side_effect = [
        response(["bad"]),
        response(_mock_wttr_response()),
    ]

    result = get_weather("London", preferred_source="open-meteo", session=session)
    assert result["source"] == "wttr"


# ---------------------------------------------------------------------------
# Traditional Chinese detection
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "city",
    ["台中", "臺中", "台南", "臺南", "高雄", "桃園", "桃园", "新竹", "基隆", "新北"],
)
def test_resolve_language_taiwan_cities_return_zh_hant(city):
    assert _resolve_language("auto", city) == "zh-Hant"


def test_resolve_language_macau_traditional_returns_zh_hant():
    assert _resolve_language("auto", "澳門") == "zh-Hant"


# ---------------------------------------------------------------------------
# Tool output contract
# ---------------------------------------------------------------------------
def _tool_yaml() -> dict:
    yaml_path = Path(__file__).resolve().parents[1] / "tools" / "weather_lookup.yaml"
    with yaml_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_output_schema_covers_every_emitted_field():
    declared = set(_tool_yaml()["output_schema"]["properties"].keys())
    assert declared == set(_OUTPUT_FIELDS) | {"raw"}


@pytest.mark.parametrize(
    "field",
    ["temperature", "feels_like", "humidity", "wind_speed"],
)
def test_numeric_output_fields_allow_null_failures(field):
    schema = _tool_yaml()["output_schema"]["properties"][field]
    assert "null" in schema["type"]


def _wttr_request_stub(self, method, url, **kwargs):
    resp = Mock(spec=requests.Response)
    resp.json.return_value = _mock_wttr_response()
    resp.raise_for_status.return_value = None
    resp.status_code = 200
    return resp


def _invoke_tool(tool_parameters, request_stub=None):
    tool = WeatherLookupTool.from_credentials({})
    with patch.object(requests.Session, "request", request_stub or _wttr_request_stub):
        return list(tool.invoke(tool_parameters))


def _json_payload(messages: list[Any]) -> dict[str, Any]:
    for message in messages:
        if message.type.name == "JSON":
            return cast(dict[str, Any], message.message.json_object)
    raise AssertionError("no JSON message emitted")


def _text_output(messages: list[Any]) -> str:
    for message in messages:
        if message.type.name == "TEXT":
            return cast(str, message.message.text)
    raise AssertionError("no text message emitted")


def test_json_payload_matches_output_schema():
    payload = _json_payload(_invoke_tool({"location": "London"}))
    assert set(payload.keys()) == set(_OUTPUT_FIELDS)


def test_include_raw_json_emits_only_declared_keys():
    payload = _json_payload(
        _invoke_tool({"location": "London", "include_raw_json": True})
    )
    assert set(payload.keys()) == set(_OUTPUT_FIELDS) | {"raw"}
    assert "current_condition" in payload["raw"]


def test_tool_text_includes_actual_source():
    text = _text_output(_invoke_tool({"location": "London"}))

    assert "Source: wttr.in." in text


def test_tool_text_includes_open_meteo_attribution():
    def request_stub(self, method, url, **kwargs):
        resp = Mock(spec=requests.Response)
        resp.raise_for_status.return_value = None
        resp.status_code = 200
        if "geocoding" in url:
            resp.json.return_value = _mock_open_meteo_geocode_response()
        else:
            resp.json.return_value = _mock_open_meteo_forecast_response()
        return resp

    text = _text_output(
        _invoke_tool(
            {"location": "London", "source_preference": "open-meteo"},
            request_stub=request_stub,
        )
    )

    assert "Open-Meteo attribution" in text


def test_tool_emits_every_declared_variable():
    messages = _invoke_tool({"location": "London"})
    variables = {
        getattr(message.message, "variable_name", None)
        for message in messages
        if message.type.name == "VARIABLE"
    }
    assert variables - {None} == set(_OUTPUT_FIELDS)


def test_error_message_without_location_omits_placeholder():
    message = _error_message("", "Location is required.", "en-US")
    assert "(empty)" not in message
    assert "Location is required." in message


# ---------------------------------------------------------------------------
# Transliteration-aware geocoding queries
# ---------------------------------------------------------------------------
def test_open_meteo_queries_romanizes_hangul():
    queries = _open_meteo_queries("서울", "ko")
    assert queries[0] == ("seoul", "en")
    assert ("서울", "ko") in queries


def test_open_meteo_queries_romanizes_kana():
    queries = _open_meteo_queries("とうきょう", "ja")
    assert queries[0] == ("tokyo", "en")


def test_open_meteo_queries_expands_japanese_place_names():
    queries = _open_meteo_queries("横浜", "ja")
    assert queries[:2] == [("横浜市", "ja"), ("横浜都", "ja")]
    assert ("横浜", "ja") in queries


def test_open_meteo_queries_keeps_chinese_names_as_is():
    queries = _open_meteo_queries("北京", "zh-Hans")
    assert queries[0] == ("北京", "zh")


def test_open_meteo_queries_leaves_latin_names_alone():
    assert _open_meteo_queries("London", "en-US") == [("London", "en")]


def test_open_meteo_queries_uses_latin_alias_for_taiwan():
    queries = _open_meteo_queries("台北", "zh-Hant")
    assert queries[0] == ("Taipei", "en")


def test_open_meteo_queries_keeps_mainland_chinese_name_first():
    queries = _open_meteo_queries("北京", "zh-Hans")
    assert queries[0] == ("北京", "zh")


def test_open_meteo_queries_strips_query_noise_before_romanizing():
    queries = _open_meteo_queries("서울 날씨", "ko")
    assert queries[0] == ("seoul", "en")


def test_open_meteo_queries_does_not_fragment_a_pure_kana_name():
    # "きょうと" must stay whole; "きょう" resolves to Kyo in Comoros.
    assert _open_meteo_queries("きょうと", "ja") == [
        ("kyoto", "en"),
        ("きょうと", "ja"),
    ]


def test_kana_input_is_treated_as_japanese():
    assert _infer_country_hints("きょうと") == ["JP"]


def test_get_weather_uses_open_meteo_for_hangul_even_when_wttr_is_preferred():
    """wttr.in answers native-script Korean with a different place entirely."""
    session = Mock(spec=requests.Session)

    def side_effect(method, url, **kwargs):
        if "wttr.in" in url:
            raise AssertionError("wttr.in must not be queried for Hangul input")
        resp = Mock(spec=requests.Response)
        if "geocoding" in url:
            resp.json.return_value = _mock_open_meteo_geocode_response(
                "서울특별시", "KR"
            )
        else:
            resp.json.return_value = _mock_open_meteo_forecast_response()
        resp.raise_for_status.return_value = None
        return resp

    session.request.side_effect = side_effect
    result = get_weather(
        "서울", language="ko", preferred_source="wttr", session=session
    )
    assert result["source"] == "open-meteo"


def test_get_weather_uses_open_meteo_for_kana_even_when_wttr_is_preferred():
    session = Mock(spec=requests.Session)

    def side_effect(method, url, **kwargs):
        if "wttr.in" in url:
            raise AssertionError("wttr.in must not be queried for kana input")
        resp = Mock(spec=requests.Response)
        if "geocoding" in url:
            resp.json.return_value = _mock_open_meteo_geocode_response("東京都", "JP")
        else:
            resp.json.return_value = _mock_open_meteo_forecast_response()
        resp.raise_for_status.return_value = None
        return resp

    session.request.side_effect = side_effect
    result = get_weather(
        "とうきょう", language="ja", preferred_source="wttr", session=session
    )
    assert result["source"] == "open-meteo"


def test_get_weather_uses_open_meteo_for_japanese_han_when_wttr_is_preferred():
    """Recognized Japanese Han names must not fall through to wttr.in."""
    session = Mock(spec=requests.Session)

    def side_effect(method, url, **kwargs):
        if "wttr.in" in url:
            raise AssertionError("wttr.in must not be queried for Japanese Han input")
        resp = Mock(spec=requests.Response)
        if "geocoding" in url:
            resp.json.return_value = _mock_open_meteo_geocode_response("岐阜市", "JP")
        else:
            resp.json.return_value = _mock_open_meteo_forecast_response()
        resp.raise_for_status.return_value = None
        return resp

    session.request.side_effect = side_effect
    result = get_weather(
        "岐阜", language="auto", preferred_source="wttr", session=session
    )
    assert result["source"] == "open-meteo"


def test_get_weather_queries_open_meteo_with_the_romanized_name():
    session = Mock(spec=requests.Session)
    requested_names: list[str] = []

    def side_effect(method, url, **kwargs):
        if "geocoding" in url:
            requested_names.append(kwargs["params"]["name"])
            resp = Mock(spec=requests.Response)
            resp.json.return_value = _mock_open_meteo_geocode_response(
                "서울특별시", "KR"
            )
            resp.raise_for_status.return_value = None
            return resp
        resp = Mock(spec=requests.Response)
        resp.json.return_value = _mock_open_meteo_forecast_response()
        resp.raise_for_status.return_value = None
        return resp

    session.request.side_effect = side_effect
    get_weather("서울", language="ko", session=session)
    assert requested_names[0] == "seoul"


def test_get_weather_summary_reports_the_resolved_place():
    session = _build_mock_session()
    result = get_weather("서울", language="ko", session=session)
    assert result["location"]
    assert result["summary"].startswith(result["location"])
