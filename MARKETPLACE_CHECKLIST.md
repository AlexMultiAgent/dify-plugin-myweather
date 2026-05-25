# Marketplace Pre-Submit Checklist

Check each item before submitting to the Dify Marketplace.

## PR Metadata

- **Plugin Author**: alexmultiagent
- **Plugin Name**: myweather
- **Repository URL**: https://github.com/AlexMultiAgent/myweather

## Submission Type

- [x] Version update for existing plugin

## Checklist (13 items)

- [ ] **1. Unique plugin name** — `myweather` is unique in the Dify Marketplace; search confirms no conflicts.
- [ ] **2. Brand alignment** — Plugin name `myweather` reflects the weather-lookup functionality.
- [ ] **3. Works end-to-end** — Tested via Dify remote debugging on both Community Edition and Cloud Version; production-ready.
- [ ] **4. README in English** — Includes setup steps, usage instructions, tool parameters, output variables, and language support table. No exaggerated claims, ads, self-promotion, offensive content, real user data in screenshots, or dead links.
- [ ] **5. Clear error messages** — Required field `location` is validated; all error paths return localized, human-readable messages in 5 languages.
- [ ] **6. Authentication documented** — This plugin intentionally requires no API key; documented in README and provider code.
- [ ] **7. Privacy policy ready** — `PRIVACY.md` exists, lists all third-party services (wttr.in, geocoding-api.open-meteo.com, api.open-meteo.com), and follows Dify Plugin Privacy Protection Guidelines.
- [ ] **8. Credentials handled securely** — No API keys or secrets are required, hardcoded, or exposed.
- [ ] **9. Performance acceptable** — Single HTTP call per source with 12 s timeout; does not noticeably degrade Dify.
- [ ] **10. Manifest & version consistency** — Version `0.1.2` matches across `manifest.yaml`, `pyproject.toml`, and `USER_AGENT` in `tools/weather_logic.py`. Author `alexmultiagent` is consistent across `manifest.yaml`, `provider/myweather.yaml`, and `tools/weather_lookup.yaml`.
- [ ] **11. Multi-language coverage** — All user-facing strings have translations in 5 languages: `en_US`, `zh_Hans`, `zh_Hant`, `ja_JP`, `ko_KR`. Tool parameter labels and `human_description` fields are present for all parameters.
- [ ] **12. Output schema matches implementation** — `output_schema` in `tools/weather_lookup.yaml` covers all 14 output fields emitted by `weather_lookup.py`.
- [ ] **13. Packaging succeeds** — `dify plugin package ./dify-weather-plugin` runs without errors; generated `.difypkg` includes all required files.

## Manifest

- [ ] `manifest.yaml` version matches the packaged `.difypkg` version AND the `USER_AGENT` string in `tools/weather_logic.py`
- [ ] `author` field is consistent across `manifest.yaml`, `provider/myweather.yaml`, and `tools/weather_lookup.yaml`
- [ ] `created_at` reflects the initial publish date (`2026-04-08T00:00:00Z`)
- [ ] `icon` points to `_assets/icon.svg`
- [ ] `privacy` points to `./PRIVACY.md`
- [ ] `tags` are valid Dify enum values (`weather`)
- [ ] `meta.runner.language` is `python` and `version` matches the tested runtime (`3.12`)

## Provider

- [ ] `provider/myweather.yaml` identity matches `manifest.yaml`
- [ ] Tool reference `tools/weather_lookup.yaml` resolves correctly

## Tool

- [ ] `tools/weather_lookup.yaml` identity matches author
- [ ] All parameters have `label` and `human_description` in all 5 languages (en_US, zh_Hans, zh_Hant, ja_JP, ko_KR)
- [ ] `output_schema` covers all output variables emitted by `weather_lookup.py`
- [ ] `llm_description` is present for the `location` parameter

## Privacy & Compliance

- [ ] `PRIVACY.md` exists and lists all third-party services
- [ ] Open-Meteo CC BY 4.0 compliance notice is emitted when source is `open-meteo`
- [ ] Attribution links are correct in README and code comments

## Packaging

- [ ] `dify plugin package ./dify-weather-plugin` succeeds without errors
- [ ] Generated `.difypkg` includes all required files
- [ ] Plugin installs and runs in a Dify instance

## Functional

- [ ] `wttr` primary source works for English and CJK locations
- [ ] `open-meteo` primary source works for English and CJK locations
- [ ] Fallback triggers correctly when the primary source fails
- [ ] Language auto-detection works for Korean (Hangul), Japanese (kana), Chinese (CJK)
- [ ] Explicit language selection overrides auto-detection
- [ ] `uscs` unit selection shows Fahrenheit and mph
- [ ] `include_raw_json` toggles the raw upstream payload
- [ ] Retry logic handles transient network errors (ConnectionError, Timeout)
- [ ] CJK query noise tokens are stripped in length order (longest first)
- [ ] English query noise uses word-boundary removal (avoids corrupting "now" in "Snowville")
- [ ] `_as_bool` uses explicit allowlist/denylist for robust boolean parsing
- [ ] `_to_int` uses `round()` for mathematically correct float→int conversion
