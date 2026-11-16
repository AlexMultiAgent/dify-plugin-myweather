from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.weather_logic import WeatherLookupError, _resolve_language, get_weather


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return False


_LQ = "“"
_RQ = "”"

_OUTPUT_FIELDS = (
    "source",
    "source_display",
    "language",
    "location",
    "condition",
    "temperature",
    "temperature_unit",
    "feels_like",
    "humidity",
    "wind_speed",
    "wind_speed_unit",
    "summary",
    "open_meteo_compliance_notice",
    "rate_limit_notice",
)


def _error_message(location: str, exc: str, language: str) -> str:
    if not location:
        if language == "zh-Hans":
            return f"天气查询失败：{exc}"
        if language == "zh-Hant":
            return f"天氣查詢失敗：{exc}"
        if language == "ja":
            return f"天気取得に失敗しました：{exc}"
        if language == "ko":
            return f"날씨 조회 실패: {exc}"
        return f"Weather lookup failed: {exc}"

    if language == "zh-Hans":
        return f"查询 {_LQ}{location}{_RQ} 天气失败：{exc}"
    if language == "zh-Hant":
        return f"查詢 {_LQ}{location}{_RQ} 天氣失敗：{exc}"
    if language == "ja":
        return f"{_LQ}{location}{_RQ} の天気取得に失敗しました：{exc}"
    if language == "ko":
        return f"{_LQ}{location}{_RQ} 날씨 조회 실패: {exc}"
    return f"Weather lookup failed for '{location}': {exc}"


def _empty_result(lang: str, loc: str, error_text: str) -> dict[str, Any]:
    return {
        "source": "",
        "source_display": "",
        "language": lang,
        "location": loc,
        "condition": "",
        "temperature": None,
        "temperature_unit": "",
        "feels_like": None,
        "humidity": None,
        "wind_speed": None,
        "wind_speed_unit": "",
        "summary": error_text,
        "open_meteo_compliance_notice": "",
        "rate_limit_notice": "",
    }


class WeatherLookupTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        location = str(tool_parameters.get("location", "")).strip()

        if not location:
            error_text = _error_message("", "Location is required.", "en-US")
            empty = _empty_result("en-US", "", error_text)
            for field in _OUTPUT_FIELDS:
                yield self.create_variable_message(field, empty[field])
            yield self.create_json_message(empty)
            yield self.create_text_message(error_text)
            return

        units = str(tool_parameters.get("units", "metric")).strip() or "metric"
        source_preference = str(tool_parameters.get("source_preference", "open-meteo")).strip() or "open-meteo"
        language = str(tool_parameters.get("language", "auto")).strip() or "auto"
        include_raw_json = _as_bool(tool_parameters.get("include_raw_json", False))

        try:
            weather = get_weather(
                location=location,
                units=units,
                preferred_source=source_preference,
                language=language,
            )
        except WeatherLookupError as exc:
            resolved_lang = _resolve_language(language, location)
            error_text = _error_message(location, str(exc), resolved_lang)
            empty = _empty_result(resolved_lang, location, error_text)
            for field in _OUTPUT_FIELDS:
                yield self.create_variable_message(field, empty[field])
            yield self.create_json_message(empty)
            yield self.create_text_message(error_text)
            return

        for field in _OUTPUT_FIELDS:
            yield self.create_variable_message(field, weather[field])

        payload = {field: weather[field] for field in _OUTPUT_FIELDS}
        if include_raw_json:
            payload["raw"] = weather.get("raw")
        yield self.create_json_message(payload)

        yield self.create_text_message(weather["summary"])
