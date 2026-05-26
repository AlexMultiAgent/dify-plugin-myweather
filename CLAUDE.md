# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MyWeather is a Dify plugin that provides weather lookups without requiring an API key. It supports English, Simplified Chinese, Traditional Chinese, Japanese, and Korean input/output, using wttr.in and Open-Meteo as upstream weather sources with automatic fallback.

## Build & Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run plugin locally (for remote debugging against a Dify instance)
python -m main

# Run tests
pytest

# Package for distribution (.difypkg file) — must be run from outside the plugin directory
dify plugin package /path/to/dify-plugin-myweather -o /path/to/dify-plugin-myweather/myweather.difypkg
```

## Architecture

### Dify Plugin Framework (dify_plugin >= 0.7.4)

The plugin follows Dify's standard structure: `main.py` creates a `Plugin(DifyPluginEnv(MAX_REQUEST_TIMEOUT=120))` and calls `plugin.run()`. The framework auto-discovers providers and tools from the YAML manifests.

### Three-Layer Dify Structure

1. **`main.py`** — Plugin entry point. Bootstraps the Dify plugin runtime.
2. **`provider/myweather.py`** + **`provider/myweather.yaml`** — Provider layer. `MyWeatherProvider` extends `ToolProvider` and requires no credentials (no API key). The YAML declares which tools belong to this provider.
3. **`tools/weather_lookup.py`** + **`tools/weather_lookup.yaml`** — Tool layer. `WeatherLookupTool` extends `Tool` and implements `_invoke()` as a generator yielding `ToolInvokeMessage` objects (variable messages, text messages, JSON messages). The YAML defines parameters, output schema, and LLM-facing descriptions in all 5 supported languages.

### Core Logic (`tools/weather_logic.py`)

The `get_weather()` function is the main entry point. It:
- Resolves the output language via `_resolve_language()` — detects from input using Unicode script analysis (Hangul → ko, kana → ja, CJK → zh-Hans, else en-US), with country-hint disambiguation for kanji-only text
- Cleans CJK location queries by stripping noise tokens and splitting on conjunction markers
- Iterates through source order (primary → fallback), trying `_candidate_locations()` for each
- Delegates to `_fetch_from_wttr()` or `_fetch_from_open_meteo()` for the actual HTTP calls
- Post-processes: unit normalization, condition translation, compliance notices, summary building
- Returns a dict with all 14 output fields

**HTTP layer**: `_retry_request()` wraps `requests.Session.request()` with up to 2 retries (exponential backoff) for `ConnectionError`/`Timeout`, but does NOT retry HTTP errors (4xx/5xx).

**Open-Meteo geocoding**: `_build_open_meteo_geocode_params()` generates ordered attempts varying language code and country hint. `_select_open_meteo_candidate()` scores results by name match, country hint, feature code (PPLC > PPLA > PPL), and population.

### Translations (`tools/translations.py`)

Static dictionaries for weather condition translations:
- `WEATHER_TRANSLATIONS_ZH_HANS` — full Simplified Chinese (160+ terms)
- `WEATHER_TRANSLATIONS_ZH_HANT` — Traditional Chinese, built as `ZH_HANS` + overrides for terms that differ
- `WEATHER_TRANSLATIONS_JA` — Japanese (160+ terms)
- `WEATHER_TRANSLATIONS_KO` — Korean (160+ terms)
- `WEATHER_CODE_DESCRIPTIONS` — Open-Meteo WMO weather codes → English descriptions

### Version Bumping

When the version changes, update all three locations:
1. `manifest.yaml` — `version` and `meta.version`
2. `pyproject.toml` — `project.version`
3. `tools/weather_logic.py` — `USER_AGENT` string constant

### Remote Debugging

Copy `.env.example` to `.env`, fill in the Dify debug instance credentials, then run `python -m main`. The Dify instance connects to this local process to execute the plugin.

## Tests

Tests are in `tests/test_weather_logic.py` using pytest with `unittest.mock`. They cover:
- Language detection and resolution (including edge cases like Hangul+CJK and Kana+CJK mixed text)
- CJK location fragment extraction and noise removal
- Open-Meteo candidate selection scoring
- Unit conversion helpers
- Summary building in multiple languages
- `_as_bool` parsing and `_error_message` localization
- HTTP retry behavior (success, retry, exhaustion, HTTP error passthrough)
- Full `get_weather()` integration with mocked sessions, including fallback scenarios, rate-limit notices, and USCS units

No API keys or live network access are required for testing — all HTTP calls are mocked.
