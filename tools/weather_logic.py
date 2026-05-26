from __future__ import annotations

import logging
import re
import time
from typing import Any
from urllib.parse import quote_plus

import requests

logger = logging.getLogger(__name__)

from tools.translations import (
    WEATHER_CODE_DESCRIPTIONS,
    WEATHER_TRANSLATIONS_JA,
    WEATHER_TRANSLATIONS_KO,
    WEATHER_TRANSLATIONS_ZH_HANS,
    WEATHER_TRANSLATIONS_ZH_HANT,
)

WTTR_BASE_URL = "https://wttr.in"
OPEN_METEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DEFAULT_TIMEOUT = 12
# When updating the plugin version, also update manifest.yaml and pyproject.toml.
USER_AGENT = "dify-myweather-plugin/0.1.2"
OPEN_METEO_SITE_URL = "https://open-meteo.com"
OPEN_METEO_LICENCE_URL = "https://open-meteo.com/en/licence"
OPEN_METEO_TERMS_URL = "https://open-meteo.com/en/terms"
OPEN_METEO_PRICING_URL = "https://open-meteo.com/en/pricing"
WTTR_HELP_URL = "https://wttr.in/:help"

LANGUAGE_VALUES = frozenset({"auto", "en-US", "zh-Hans", "zh-Hant", "ja", "ko"})

_TRANSLATION_MAP = {
    "en-US": None,
    "zh-Hans": WEATHER_TRANSLATIONS_ZH_HANS,
    "zh-Hant": WEATHER_TRANSLATIONS_ZH_HANT,
    "ja": WEATHER_TRANSLATIONS_JA,
    "ko": WEATHER_TRANSLATIONS_KO,
}

ZH_HANS_QUERY_NOISE_TOKENS = [
    "天气预报",
    "天气",
    "温度",
    "气温",
    "现在",
    "今天",
    "明天",
    "后天",
    "如何",
    "怎么样",
    "请问",
    "帮我",
    "帮忙",
    "查询",
    "查一下",
    "查下",
    "看一下",
    "看下",
    "告诉我",
    "一下",
    "会不会",
    "是否",
    "有没有",
    "多少",
    "几度",
]

ZH_HANT_QUERY_NOISE_TOKENS = [
    "天氣預報",
    "天氣",
    "溫度",
    "氣溫",
    "現在",
    "今天",
    "明天",
    "後天",
    "如何",
    "怎麼樣",
    "請問",
    "幫我",
    "幫忙",
    "查詢",
    "查一下",
    "查下",
    "看一下",
    "看下",
    "告訴我",
    "一下",
    "會不會",
    "是否",
    "有沒有",
    "多少",
    "幾度",
]

JA_QUERY_NOISE_TOKENS = [
    "天気予報",
    "天気",
    "気温",
    "温度",
    "今",
    "今日",
    "明日",
    "明後日",
    "どう",
    "どんな",
    "教えて",
    "調べて",
    "見て",
    "確認",
    "ください",
    "お願い",
    "ますか",
    "でしょう",
    "かな",
    "かしら",
    "?",
]

KO_QUERY_NOISE_TOKENS = [
    "날씨예보",
    "일기예보",
    "날씨",
    "기온",
    "온도",
    "지금",
    "오늘",
    "내일",
    "모레",
    "어때",
    "어떻게",
    "알려줘",
    "찾아줘",
    "검색",
    "확인",
    "해줘",
    "주세요",
    "부탁",
    "할까",
    "할까요",
]

_NOISE_TOKENS_MAP = {
    "zh-Hans": ZH_HANS_QUERY_NOISE_TOKENS,
    "zh-Hant": ZH_HANT_QUERY_NOISE_TOKENS,
    "ja": JA_QUERY_NOISE_TOKENS,
    "ko": KO_QUERY_NOISE_TOKENS,
}

ZH_HANS_QUERY_SPLIT_MARKERS = [
    "是不是",
    "还是",
    "和",
    "与",
    "跟",
    "及",
    "、",
    "，",
    ",",
    "/",
    "|",
    "对比",
    "比较",
    "vs",
    "VS",
]

ZH_HANT_QUERY_SPLIT_MARKERS = [
    "是不是",
    "還是",
    "和",
    "與",
    "跟",
    "及",
    "、",
    "，",
    ",",
    "/",
    "|",
    "對比",
    "比較",
    "vs",
    "VS",
]

JA_QUERY_SPLIT_MARKERS = [
    "か",
    "と",
    "や",
    "または",
    "それとも",
    "あるいは",
    "もしくは",
    "と比べて",
    "、",
    "，",
    ",",
    "/",
    "|",
    "vs",
    "VS",
]

KO_QUERY_SPLIT_MARKERS = [
    "랑",
    "하고",
    "과",
    "와",
    "또는",
    "혹은",
    "아니면",
    "비교",
    "、",
    "，",
    ",",
    "/",
    "|",
    "vs",
    "VS",
]

_SPLIT_MARKERS_MAP = {
    "zh-Hans": ZH_HANS_QUERY_SPLIT_MARKERS,
    "zh-Hant": ZH_HANT_QUERY_SPLIT_MARKERS,
    "ja": JA_QUERY_SPLIT_MARKERS,
    "ko": KO_QUERY_SPLIT_MARKERS,
}


_RETRY_MAX = 2
_RETRY_BACKOFF = 1.0


def _retry_request(method: str, url: str, session: requests.Session, **kwargs: Any) -> requests.Response:
    """Issue an HTTP request with retries for transient network errors."""
    last_exc: Exception | None = None
    for attempt in range(_RETRY_MAX + 1):
        try:
            response = session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            if attempt < _RETRY_MAX:
                delay = _RETRY_BACKOFF * (2 ** attempt)
                logger.debug(
                    "Retry %d/%d for %s %s after %.1fs: %s",
                    attempt + 1,
                    _RETRY_MAX,
                    method,
                    url,
                    delay,
                    exc,
                )
                time.sleep(delay)
        except requests.HTTPError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (429, 503) and attempt < _RETRY_MAX:
                last_exc = exc
                delay = _RETRY_BACKOFF * (2 ** attempt)
                logger.debug(
                    "Retry %d/%d for %s %s after %.1fs: HTTP %s",
                    attempt + 1,
                    _RETRY_MAX,
                    method,
                    url,
                    delay,
                    status,
                )
                time.sleep(delay)
            else:
                raise
    raise last_exc  # type: ignore[misc]


class WeatherLookupError(RuntimeError):
    """Raised when weather lookup cannot be completed from any source."""


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _c_to_f(value_c: float | None) -> float | None:
    if value_c is None:
        return None
    return (value_c * 9.0 / 5.0) + 32.0


def _f_to_c(value_f: float | None) -> float | None:
    if value_f is None:
        return None
    return (value_f - 32.0) * 5.0 / 9.0


def _kmh_to_mph(value_kmh: float | None) -> float | None:
    if value_kmh is None:
        return None
    return value_kmh * 0.621371


def _clean_join(parts: list[str | None]) -> str:
    return ", ".join([part.strip() for part in parts if part and part.strip()])


def _round_or_none(value: float | None, digits: int = 1) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _detect_language(text: str) -> str:
    """Detect language from text using Unicode script ranges.

    Returns one of: 'ko', 'ja', 'zh-Hans', 'en-US'
    """
    if not text:
        return "en-US"
    # Hangul Syllables (U+AC00–U+D7AF) strongly imply Korean
    if re.search(r"[가-힣]", text):
        return "ko"
    # Hiragana or Katakana strongly implies Japanese
    if re.search(r"[぀-ゟ゠-ヿ]", text):
        return "ja"
    # CJK Unified Ideographs, Extension A, or Compatibility Ideographs -> Chinese (default to zh-Hans)
    if re.search(r"[一-鿿㐀-䶿豈-﫿]", text):
        return "zh-Hans"
    return "en-US"


def _resolve_language(param_language: str | None, location_text: str) -> str:
    """Resolve the user-facing language parameter to a canonical code."""
    lang = (param_language or "auto").strip()
    if lang not in LANGUAGE_VALUES:
        lang = "auto"
    if lang == "auto":
        detected = _detect_language(location_text)
        # Kanji-only text is ambiguous (could be zh-Hans or ja). Use country
        # hints from the location text to disambiguate.
        if detected == "zh-Hans":
            hints = _infer_country_hints(location_text)
            if "JP" in hints:
                return "ja"
            if "KR" in hints:
                return "ko"
            if "TW" in hints or "HK" in hints or "MO" in hints:
                return "zh-Hant"
        return detected
    return lang


def _is_cjk_language(language: str) -> bool:
    """Check whether the language is a CJK variant that needs space stripping etc."""
    return language in ("zh-Hans", "zh-Hant", "ja", "ko")


def _contains_cjk_chars(text: str) -> bool:
    """Check if text contains CJK, Japanese, or Korean characters (for display logic)."""
    if not text:
        return False
    return bool(re.search(r"[一-鿿㐀-䶿豈-﫿぀-ゟ゠-ヿ가-힣]", text))


def _normalize_condition_key(condition: str) -> str:
    condition = (condition or "").strip().lower()
    return re.sub(r"\s+", " ", condition)


def _translate_condition(condition: str, language: str) -> str:
    if language == "en-US":
        return condition
    key = _normalize_condition_key(condition)
    trans_map = _TRANSLATION_MAP.get(language)
    if trans_map is None:
        return condition
    return trans_map.get(key, condition or trans_map.get("unknown", "Unknown"))


def _extract_cjk_location_fragments(text: str, language: str = "zh-Hans") -> list[str]:
    if not text:
        return []

    cleaned = text
    noise_tokens = _NOISE_TOKENS_MAP.get(language, [])
    for token in sorted(noise_tokens, key=len, reverse=True):
        cleaned = cleaned.replace(token, " ")

    cleaned = re.sub(r"[？?！!。；;：:（）()\[\]{}]", " ", cleaned)
    split_markers = _SPLIT_MARKERS_MAP.get(language, [])
    split_pattern = "|".join(sorted([re.escape(item) for item in split_markers], key=len, reverse=True))
    parts = re.split(split_pattern, cleaned) if split_pattern else [cleaned]

    fragments: list[str] = []
    for part in parts:
        candidate = re.sub(r"\s+", " ", part).strip("，,。.;； ")
        candidate = candidate.strip("的").strip("の")
        if _contains_cjk_chars(candidate) and language != "ko":
            candidate = candidate.replace(" ", "")
        if candidate and candidate not in fragments:
            fragments.append(candidate)

    return fragments


def _normalize_location_key(text: str) -> str:
    normalized = (text or "").lower().strip()
    return re.sub(r"[\s,，。.;；:_\-/\\'`]+", "", normalized)


def _infer_country_hints(location: str) -> list[str]:
    raw = location or ""
    lowered = raw.lower()

    if "香港" in raw or "hong kong" in lowered:
        return ["HK"]
    if "澳门" in raw or "macau" in lowered or "macao" in lowered:
        return ["MO"]
    if any(token in raw for token in ["台湾", "台灣", "臺灣", "台北", "臺北"]) or "taiwan" in lowered or "taipei" in lowered:
        return ["TW"]
    if "中国" in raw or "中國" in raw or "大陆" in raw or "大陸" in raw or "china" in lowered:
        return ["CN"]
    if any(token in raw for token in [
        "日本", "東京", "大阪", "京都", "北海道", "沖縄", "名古屋", "福岡",
        "札幌", "広島", "横浜", "神戸", "仙台", "新宿", "渋谷", "千葉",
        "埼玉", "神奈川", "長崎", "奈良", "鹿児島",
    ]) or any(tok in lowered for tok in [
        "tokyo", "osaka", "kyoto", "hokkaido", "okinawa", "nagoya", "fukuoka",
        "sapporo", "hiroshima", "yokohama", "kobe", "sendai",
    ]):
        return ["JP"]
    if any(token in raw for token in [
        "한국", "서울", "부산", "인천", "대구", "대전", "광주", "울산",
        "제주", "수원", "성남", "고양", "용인", "청주", "전주", "포항",
        "경주", "강릉", "속초", "여수", "목포", "춘천", "원주",
    ]) or any(tok in lowered for tok in [
        "korea", "seoul", "busan", "incheon", "daegu", "daejeon",
        "gwangju", "ulsan", "jeju", "suwon", "seongnam",
    ]):
        return ["KR"]

    return []


def _build_open_meteo_geocode_params(location: str, language: str = "en-US") -> list[dict[str, Any]]:
    if language == "ja":
        api_languages = ["ja", "en"]
    elif language in ("zh-Hans", "zh-Hant"):
        api_languages = ["zh", "en"]
    elif language == "ko":
        api_languages = ["ko", "en"]
    else:
        api_languages = ["en"]

    country_hints = _infer_country_hints(location)
    country_candidates: list[str | None] = country_hints + [None]

    attempts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for country in country_candidates:
        for lang in api_languages:
            key = f"{lang}|{country or ''}"
            if key in seen:
                continue
            seen.add(key)

            params: dict[str, Any] = {
                "name": location,
                "count": 8,
                "language": lang,
                "format": "json",
            }
            if country:
                params["countryCode"] = country
            attempts.append(params)

    return attempts


def _select_open_meteo_candidate(
    candidates: list[dict[str, Any]],
    query: str,
    country_hint: str | None = None,
    language: str = "en-US",
) -> dict[str, Any]:
    if not candidates:
        raise ValueError("candidates must not be empty")

    is_cjk = _is_cjk_language(language)
    query_basis = _normalize_cjk_location_display(query, language) if is_cjk else query
    query_key = _normalize_location_key(query_basis)

    best_match = candidates[0]
    best_score = float("-inf")

    for index, candidate in enumerate(candidates):
        score = 0.0
        name_key = _normalize_location_key(str(candidate.get("name") or ""))

        if query_key and name_key == query_key:
            score += 220.0
        elif query_key and query_key in name_key:
            score += 140.0
        elif query_key and name_key and name_key in query_key:
            score += 70.0

        candidate_country = str(candidate.get("country_code") or "").upper()
        if country_hint and candidate_country == country_hint:
            score += 90.0
        elif country_hint and candidate_country:
            score -= 35.0

        feature_code = str(candidate.get("feature_code") or "").upper()
        if feature_code == "PPLC":
            score += 55.0
        elif feature_code.startswith("PPLA"):
            score += 45.0
        elif feature_code.startswith("PPL"):
            score += 25.0

        population = _to_int(candidate.get("population")) or 0
        score += min(population / 500000.0, 35.0)
        score += max(0, 8 - index)

        if score > best_score:
            best_score = score
            best_match = candidate

    return best_match


def _candidate_locations(query: str, language: str = "en-US") -> list[str]:
    candidates: list[str] = []
    base = query.strip()
    if base:
        candidates.append(base)

    lowered = base.lower()
    english_noise = [
        "weather",
        "forecast",
        "temperature",
        "temp",
        "right now",
        "now",
        "today",
        "tomorrow",
        "please",
        "show me",
        "for",
        "in",
        "at",
    ]
    cleaned_en = lowered
    for token in sorted(english_noise, key=len, reverse=True):
        cleaned_en = re.sub(r"\b" + re.escape(token) + r"\b", " ", cleaned_en)
    cleaned_en = re.sub(r"[^a-z0-9\s\-']", " ", cleaned_en)
    cleaned_en = re.sub(r"\s+", " ", cleaned_en).strip(" -'")
    if cleaned_en and cleaned_en != lowered:
        candidates.append(cleaned_en.title())

    # CJK query cleanup and segmentation.
    if _is_cjk_language(language):
        fragments = _extract_cjk_location_fragments(base, language)
        for frag in fragments:
            if frag and frag != base:
                candidates.append(frag)

    # De-duplicate while preserving order.
    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _normalize_cjk_location_display(text: str, language: str = "zh-Hans") -> str:
    fragments = _extract_cjk_location_fragments(text or "", language)
    if fragments:
        return fragments[0]
    cleaned = re.sub(r"[？！!。；;：:（）\[\]{}?]", " ", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip("，,。.;； ")
    return cleaned or text


def _fetch_from_wttr(location: str, session: requests.Session) -> dict[str, Any]:
    encoded_location = quote_plus(location.strip())
    logger.info("Fetching weather from wttr.in for location=%s", location)
    response = _retry_request(
        "GET",
        f"{WTTR_BASE_URL}/{encoded_location}",
        session,
        params={"format": "j1"},
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    )

    payload = response.json()
    current = (payload.get("current_condition") or [{}])[0]
    nearest = (payload.get("nearest_area") or [{}])[0]

    area_name = ((nearest.get("areaName") or [{}])[0]).get("value")
    region_name = ((nearest.get("region") or [{}])[0]).get("value")
    country_name = ((nearest.get("country") or [{}])[0]).get("value")
    resolved_location = _clean_join([area_name, region_name, country_name]) or location

    condition = ((current.get("weatherDesc") or [{}])[0]).get("value") or "Unknown"

    temp_c = _to_float(current.get("temp_C"))
    temp_f = _to_float(current.get("temp_F"))
    feels_c = _to_float(current.get("FeelsLikeC"))
    feels_f = _to_float(current.get("FeelsLikeF"))
    wind_kmh = _to_float(current.get("windspeedKmph"))

    if temp_c is None and temp_f is not None:
        temp_c = _f_to_c(temp_f)
    if temp_f is None and temp_c is not None:
        temp_f = _c_to_f(temp_c)
    if feels_c is None and feels_f is not None:
        feels_c = _f_to_c(feels_f)
    if feels_f is None and feels_c is not None:
        feels_f = _c_to_f(feels_c)

    return {
        "source": "wttr",
        "query_location": location,
        "location": resolved_location,
        "condition": condition,
        "temperature_c": temp_c,
        "temperature_f": temp_f,
        "feels_like_c": feels_c,
        "feels_like_f": feels_f,
        "humidity": _to_int(current.get("humidity")),
        "wind_speed_kmh": wind_kmh,
        "wind_speed_mph": _kmh_to_mph(wind_kmh),
        "raw": payload,
    }


def _fetch_from_open_meteo(location: str, session: requests.Session, language: str = "en-US") -> dict[str, Any]:
    geocode_payload: dict[str, Any] | None = None
    match: dict[str, Any] | None = None
    latitude: float | None = None
    longitude: float | None = None
    geocode_errors: list[str] = []

    for geocode_params in _build_open_meteo_geocode_params(location, language):
        logger.debug(
            "Open-Meteo geocoding attempt: location=%s language=%s countryCode=%s",
            location,
            geocode_params.get("language"),
            geocode_params.get("countryCode", "*"),
        )
        geocode_resp = _retry_request(
            "GET",
            OPEN_METEO_GEOCODING_URL,
            session,
            params=geocode_params,
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        payload = geocode_resp.json()

        candidates = payload.get("results") or []
        if not candidates:
            logger.debug(
                "Open-Meteo geocoding no-match: location=%s language=%s countryCode=%s",
                location,
                geocode_params.get("language"),
                geocode_params.get("countryCode", "*"),
            )
            geocode_errors.append(
                f"language={geocode_params.get('language')},countryCode={geocode_params.get('countryCode', '*')}:no-match"
            )
            continue

        hint = str(geocode_params.get("countryCode") or "").upper() or None
        candidate = _select_open_meteo_candidate(candidates, location, country_hint=hint, language=language)
        candidate_lat = _to_float(candidate.get("latitude"))
        candidate_lon = _to_float(candidate.get("longitude"))
        if candidate_lat is None or candidate_lon is None:
            geocode_errors.append(
                f"language={geocode_params.get('language')},countryCode={geocode_params.get('countryCode', '*')}:invalid-coordinates"
            )
            continue

        geocode_payload = payload
        match = candidate
        latitude = candidate_lat
        longitude = candidate_lon
        logger.info(
            "Open-Meteo geocoding matched: %s (%s, %s) country=%s",
            match.get("name"),
            latitude,
            longitude,
            match.get("country_code", "?"),
        )
        break

    if match is None or geocode_payload is None or latitude is None or longitude is None:
        detail = "; ".join(geocode_errors) if geocode_errors else "no-candidate"
        raise WeatherLookupError(f"Open-Meteo geocoding returned no match for '{location}'. {detail}")

    resolved_location = _clean_join([match.get("name"), match.get("admin1"), match.get("country")]) or location

    weather_resp = _retry_request(
        "GET",
        OPEN_METEO_FORECAST_URL,
        session,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "timezone": "auto",
            "current": ",".join(
                [
                    "temperature_2m",
                    "apparent_temperature",
                    "relative_humidity_2m",
                    "wind_speed_10m",
                    "weather_code",
                ]
            ),
        },
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    )
    weather_payload = weather_resp.json()

    current = weather_payload.get("current") or {}
    temp_c = _to_float(current.get("temperature_2m"))
    feels_c = _to_float(current.get("apparent_temperature"))
    wind_kmh = _to_float(current.get("wind_speed_10m"))
    weather_code = _to_int(current.get("weather_code"))

    condition = WEATHER_CODE_DESCRIPTIONS.get(weather_code, "Unknown") if weather_code is not None else "Unknown"

    return {
        "source": "open-meteo",
        "query_location": location,
        "location": resolved_location,
        "condition": condition,
        "temperature_c": temp_c,
        "temperature_f": _c_to_f(temp_c),
        "feels_like_c": feels_c,
        "feels_like_f": _c_to_f(feels_c),
        "humidity": _to_int(current.get("relative_humidity_2m")),
        "wind_speed_kmh": wind_kmh,
        "wind_speed_mph": _kmh_to_mph(wind_kmh),
        "raw": {
            "geocoding": geocode_payload,
            "forecast": weather_payload,
        },
    }


def _normalize_units(data: dict[str, Any], units: str) -> dict[str, Any]:
    if units == "uscs":
        data["temperature"] = _round_or_none(data.get("temperature_f"))
        data["temperature_unit"] = "degF"
        data["feels_like"] = _round_or_none(data.get("feels_like_f"))
        data["wind_speed"] = _round_or_none(data.get("wind_speed_mph"))
        data["wind_speed_unit"] = "mph"
    else:
        data["temperature"] = _round_or_none(data.get("temperature_c"))
        data["temperature_unit"] = "degC"
        data["feels_like"] = _round_or_none(data.get("feels_like_c"))
        data["wind_speed"] = _round_or_none(data.get("wind_speed_kmh"))
        data["wind_speed_unit"] = "km/h"
    return data


def _build_open_meteo_compliance_notice(language: str = "en-US") -> str:
    if language == "zh-Hans":
        return (
            "Open-Meteo 署名与改动声明：数据来源 Open-Meteo（CC BY 4.0）；"
            "本插件进行了中文翻译、单位换算与摘要格式化。"
        )
    if language == "zh-Hant":
        return (
            "Open-Meteo 署名與改動聲明：資料來源 Open-Meteo（CC BY 4.0）；"
            "本插件進行了中文翻譯、單位換算與摘要格式化。"
        )
    if language == "ja":
        return (
            "Open-Meteo 帰属および改変通知：データソースは Open-Meteo（CC BY 4.0）です；"
            "本プラグインにより翻訳、単位変換、サマリー整形を適用しています。"
        )
    if language == "ko":
        return (
            "Open-Meteo 저작자 표시 및 변경 고지: 데이터 출처는 Open-Meteo(CC BY 4.0)입니다; "
            "본 플러그인은 번역, 단위 변환, 요약 형식화를 적용합니다."
        )
    return (
        "Open-Meteo attribution and modification notice: Data source is Open-Meteo (CC BY 4.0); "
        "this plugin applies translation, unit conversion, and summary formatting."
    )


def _is_open_meteo_rate_limited(exc: Exception) -> bool:
    if isinstance(exc, requests.HTTPError):
        response = getattr(exc, "response", None)
        if response is not None and getattr(response, "status_code", None) == 429:
            return True
    return False


def _build_open_meteo_fallback_notice(language: str = "en-US", rate_limited: bool = False) -> str:
    if language == "zh-Hans":
        if rate_limited:
            return "提示：Open-Meteo 返回 429（限流），已自动回退到 wttr.in。"
        return "提示：Open-Meteo 请求失败，已自动回退到 wttr.in。"
    if language == "zh-Hant":
        if rate_limited:
            return "提示：Open-Meteo 返回 429（限流），已自動回退到 wttr.in。"
        return "提示：Open-Meteo 請求失敗，已自動回退到 wttr.in。"
    if language == "ja":
        if rate_limited:
            return "注意：Open-Meteo が 429（レート制限）を返したため、wttr.in にフォールバックしました。"
        return "注意：Open-Meteo リクエストが失敗したため、wttr.in にフォールバックしました。"
    if language == "ko":
        if rate_limited:
            return "알림: Open-Meteo가 429(속도 제한)을 반환하여 wttr.in으로 전환했습니다."
        return "알림: Open-Meteo 요청이 실패하여 wttr.in으로 전환했습니다."

    if rate_limited:
        return "Notice: Open-Meteo returned 429 (rate limited), switched to wttr.in fallback."
    return "Notice: Open-Meteo request failed, switched to wttr.in fallback."


def _build_source_display(source: str, language: str = "en-US") -> str:
    source_name = "wttr.in" if source == "wttr" else "Open-Meteo"
    if language == "zh-Hans":
        return f"数据源：{source_name}。"
    if language == "zh-Hant":
        return f"資料來源：{source_name}。"
    if language == "ja":
        return f"データソース：{source_name}。"
    if language == "ko":
        return f"데이터 출처: {source_name}."
    return f"Source: {source_name}."


_CJK_FORMAT: dict[str, dict[str, str]] = {
    "zh-Hans": {
        "sep_location": "：",
        "sep_end": "。",
        "sep_item": "，",
        "temp_label": "温度",
        "feels_label": "体感",
        "humidity_label": "湿度",
        "wind_label": "风速",
        "wind_unit_metric": "公里/小时",
        "wind_unit_uscs": "英里/小时",
    },
    "zh-Hant": {
        "sep_location": "：",
        "sep_end": "。",
        "sep_item": "，",
        "temp_label": "溫度",
        "feels_label": "體感",
        "humidity_label": "濕度",
        "wind_label": "風速",
        "wind_unit_metric": "公里/小時",
        "wind_unit_uscs": "英里/小時",
    },
    "ja": {
        "sep_location": "：",
        "sep_end": "。",
        "sep_item": "、",
        "temp_label": "気温",
        "feels_label": "体感",
        "humidity_label": "湿度",
        "wind_label": "風速",
        "wind_unit_metric": "km/h",
        "wind_unit_uscs": "mph",
    },
    "ko": {
        "sep_location": ": ",
        "sep_end": ". ",
        "sep_item": ", ",
        "temp_label": "기온",
        "feels_label": "체감",
        "humidity_label": "습도",
        "wind_label": "풍속",
        "wind_unit_metric": "km/h",
        "wind_unit_uscs": "mph",
    },
}


def _build_summary(data: dict[str, Any], language: str = "en-US", query_location: str | None = None) -> str:
    humidity = data.get("humidity")
    temp = data.get("temperature")
    feels = data.get("feels_like")
    wind = data.get("wind_speed")
    is_metric = data.get("wind_speed_unit") == "km/h"

    fmt = _CJK_FORMAT.get(language)
    if fmt is not None:
        temp_unit_symbol = "°C" if data.get("temperature_unit") == "degC" else "°F"
        unknown_label = _translate_condition("unknown", language)
        humidity_txt = f"{humidity}%" if humidity is not None else unknown_label
        temp_txt = unknown_label if temp is None else f"{temp}"
        feels_txt = unknown_label if feels is None else f"{feels}"
        wind_txt = unknown_label if wind is None else f"{wind}"
        wind_unit = fmt["wind_unit_metric"] if is_metric else fmt["wind_unit_uscs"]
        location_display = (
            _normalize_cjk_location_display(query_location, language)
            if query_location and _contains_cjk_chars(query_location)
            else data.get("location")
        )
        weather_line = (
            f"{location_display}{fmt['sep_location']}{data.get('condition')}{fmt['sep_end']}"
            f"{fmt['temp_label']} {temp_txt}{temp_unit_symbol}{fmt['sep_item']}"
            f"{fmt['feels_label']} {feels_txt}{temp_unit_symbol}{fmt['sep_item']}"
            f"{fmt['humidity_label']} {humidity_txt}{fmt['sep_item']}"
            f"{fmt['wind_label']} {wind_txt} {wind_unit}{fmt['sep_end']}"
        )
        fallback_notice = str(data.get("rate_limit_notice") or "").strip()
        return "\n".join([weather_line, fallback_notice]) if fallback_notice else weather_line

    humidity_txt = f"{humidity}%" if humidity is not None else "n/a"
    temp_txt = "n/a" if temp is None else f"{temp}"
    feels_txt = "n/a" if feels is None else f"{feels}"
    wind_txt = "n/a" if wind is None else f"{wind}"
    temp_unit_display = data.get("temperature_unit") or "degC"
    wind_unit_display = data.get("wind_speed_unit") or "km/h"
    weather_line = (
        f"{data.get('location')}: {data.get('condition')}. "
        f"Temp {temp_txt} {temp_unit_display}, "
        f"feels like {feels_txt} {temp_unit_display}, "
        f"humidity {humidity_txt}, "
        f"wind {wind_txt} {wind_unit_display}."
    )
    fallback_notice = str(data.get("rate_limit_notice") or "").strip()
    return "\n".join([weather_line, fallback_notice]) if fallback_notice else weather_line


def get_weather(
    location: str,
    units: str = "metric",
    preferred_source: str = "wttr",
    language: str = "auto",
    session: requests.Session | None = None,
) -> dict[str, Any]:
    location = location.strip()
    if not location:
        raise WeatherLookupError("Location is required.")

    if units not in {"metric", "uscs"}:
        raise WeatherLookupError(f"Unsupported units '{units}'. Use 'metric' or 'uscs'.")

    source_order: dict[str, list[str]] = {
        "wttr": ["wttr", "open-meteo"],
        "open-meteo": ["open-meteo", "wttr"],
    }
    if preferred_source not in source_order:
        raise WeatherLookupError(
            f"Unsupported source_preference '{preferred_source}'. Use 'wttr' or 'open-meteo'."
        )

    output_language = _resolve_language(language, location)
    active_session = session or requests.Session()
    try:
        attempts = source_order[preferred_source]
        errors: dict[str, str] = {}
        location_candidates = _candidate_locations(location, output_language)
        open_meteo_failed = False
        open_meteo_rate_limited = False

        for source in attempts:
            for candidate in location_candidates:
                try:
                    if source == "wttr":
                        result = _fetch_from_wttr(candidate, active_session)
                    else:
                        result = _fetch_from_open_meteo(candidate, active_session, output_language)

                    _normalize_units(result, units)
                    result["condition"] = _translate_condition(
                        str(result.get("condition") or ""), output_language
                    )
                    result["open_meteo_compliance_notice"] = (
                        _build_open_meteo_compliance_notice(language=output_language)
                        if result.get("source") == "open-meteo"
                        else ""
                    )
                    if result.get("source") == "wttr" and open_meteo_failed:
                        result["rate_limit_notice"] = _build_open_meteo_fallback_notice(
                            language=output_language,
                            rate_limited=open_meteo_rate_limited,
                        )
                    else:
                        result["rate_limit_notice"] = ""
                    result["source_display"] = _build_source_display(
                        source=str(result.get("source") or ""),
                        language=output_language,
                    )
                    result["summary"] = _build_summary(result, language=output_language, query_location=location)
                    result["language"] = output_language
                    logger.info(
                        "Weather fetch succeeded: source=%s location=%s resolved=%s",
                        result.get("source"),
                        location,
                        result.get("location"),
                    )
                    return result
                except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
                    logger.warning(
                        "Weather fetch failed: source=%s candidate=%s error=%s",
                        source,
                        candidate,
                        exc,
                    )
                    if source == "open-meteo":
                        open_meteo_failed = True
                        if _is_open_meteo_rate_limited(exc):
                            open_meteo_rate_limited = True
                    errors[f"{source}({candidate})"] = str(exc)

        detail = "; ".join([f"{name}: {msg}" for name, msg in errors.items()]) or "unknown error"
        raise WeatherLookupError(f"All weather sources failed. {detail}")
    finally:
        if session is None:
            active_session.close()
