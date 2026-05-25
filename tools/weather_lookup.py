from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.weather_logic import WeatherLookupError, _detect_language, get_weather


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    if isinstance(value, (int, float)):
        return value != 0
    return bool(value)


_LQ = "“"
_RQ = "”"


def _error_message(location: str, exc: str, language: str) -> str:
    if language == "zh-Hans":
        return f"查询 {_LQ}{location}{_RQ} 天气失败：{exc}"
    if language == "zh-Hant":
        return f"查詢 {_LQ}{location}{_RQ} 天氣失敗：{exc}"
    if language == "ja":
        return f"{_LQ}{location}{_RQ} の天気取得に失敗しました：{exc}"
    if language == "ko":
        return f"{_LQ}{location}{_RQ} 날씨 조회 실패: {exc}"
    return f"Weather lookup failed for '{location}': {exc}"


class WeatherLookupTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        location = str(tool_parameters.get("location", "")).strip()
        if not location:
            yield self.create_text_message(
                _error_message("(empty)", "Location is required.", "en-US")
            )
            return

        units = str(tool_parameters.get("units", "metric")).strip() or "metric"
        source_preference = str(tool_parameters.get("source_preference", "wttr")).strip() or "wttr"
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
            detected_lang = _detect_language(location)
            yield self.create_text_message(_error_message(location, str(exc), detected_lang))
            return

        yield self.create_variable_message("source", weather["source"])
        yield self.create_variable_message("source_display", weather["source_display"])
        yield self.create_variable_message("language", weather.get("language", "en-US"))
        yield self.create_variable_message("location", weather["location"])
        yield self.create_variable_message("condition", weather["condition"])
        yield self.create_variable_message("temperature", weather["temperature"])
        yield self.create_variable_message("temperature_unit", weather["temperature_unit"])
        yield self.create_variable_message("feels_like", weather["feels_like"])
        yield self.create_variable_message("humidity", weather["humidity"])
        yield self.create_variable_message("wind_speed", weather["wind_speed"])
        yield self.create_variable_message("wind_speed_unit", weather["wind_speed_unit"])
        yield self.create_variable_message("summary", weather["summary"])
        yield self.create_variable_message("open_meteo_compliance_notice", weather["open_meteo_compliance_notice"])
        yield self.create_variable_message("rate_limit_notice", weather["rate_limit_notice"])

        if include_raw_json:
            yield self.create_json_message(weather)
        else:
            yield self.create_json_message(
                {
                    "source": weather["source"],
                    "source_display": weather["source_display"],
                    "language": weather.get("language", "en-US"),
                    "location": weather["location"],
                    "condition": weather["condition"],
                    "temperature": weather["temperature"],
                    "temperature_unit": weather["temperature_unit"],
                    "feels_like": weather["feels_like"],
                    "humidity": weather["humidity"],
                    "wind_speed": weather["wind_speed"],
                    "wind_speed_unit": weather["wind_speed_unit"],
                    "summary": weather["summary"],
                    "open_meteo_compliance_notice": weather["open_meteo_compliance_notice"],
                    "rate_limit_notice": weather["rate_limit_notice"],
                }
            )

        yield self.create_text_message(weather["summary"])
