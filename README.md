# MyWeather

MyWeather is a Dify weather plugin that requires no API key.

- Primary source is selectable: `open-meteo` or `wttr`
- Default primary source: `wttr`
- Non-primary source is always used as fallback
- Supports English, Simplified Chinese, Traditional Chinese, Japanese, and Korean input and output
- Automatic language detection via Unicode script analysis

## Example Output

**English** (input: `London`)

> London, City of London Greater London, United Kingdom: Sunny. Temp 34.0°C, feels like 33.0°C, humidity 28%, wind 13.0 km/h.

**Chinese** (input: `哈尔滨`)

> 哈尔滨：晴朗。温度 19.0°C，体感 19.0°C，湿度 33%，风速 11.0 公里/小时。

Workflow: `Start (city) → Weather Lookup → Output`

## Quick Start

1. Install plugin `MyWeather` in Dify.
2. Add tool node `Weather Lookup`.
3. Set `source_preference`:
   - `wttr` (default): wttr first, Open-Meteo fallback
   - `open-meteo`: Open-Meteo first, wttr fallback
4. Pass user location text to `location`.

## Tool Parameters

- `location` (required): city, region, airport code, or place name. Supports English, Chinese, Japanese, and Korean.
- `language` (optional): output language. `auto` (default) detects from input — Hangul → Korean, hiragana/katakana → Japanese, CJK → Simplified Chinese, otherwise English. Can be set explicitly to `en-US`, `zh-Hans`, `zh-Hant`, `ja`, or `ko`.
- `units` (optional): `metric` or `uscs`.
- `source_preference` (optional): `wttr` (default) or `open-meteo`.
- `include_raw_json` (optional): include upstream raw payload in JSON output.

## Output Variables

Returned by `weather_lookup`:

- `source`: actual provider used (`wttr` or `open-meteo`).
- `source_display`: UI-ready source label (`Source: wttr.in.` or `Source: Open-Meteo.`).
- `language`: resolved output language (`en-US`, `zh-Hans`, `zh-Hant`, `ja`, or `ko`).
- `location`: resolved location name from provider.
- `condition`: weather condition text (translated when CJK/Japanese output).
- `temperature`: current temperature in selected units.
- `temperature_unit`: `degC` or `degF`.
- `feels_like`: feels-like temperature.
- `humidity`: relative humidity percentage.
- `wind_speed`: wind speed in selected units.
- `wind_speed_unit`: `km/h` or `mph`.
- `summary`: concise weather sentence without inline source text (localized).
- `open_meteo_compliance_notice`: Open-Meteo attribution plus modification declaration (only when source is Open-Meteo).
- `rate_limit_notice`: fallback notice (only when Open-Meteo fails, including HTTP 429, and fallback is triggered).

## Language Support

| Language | Detection | Weather Translation | Geocoding |
| --- | --- | --- | --- |
| English (en-US) | Default | Passthrough | Standard |
| Simplified Chinese (zh-Hans) | CJK characters | Full (160+ terms) | `zh` + `en` |
| Traditional Chinese (zh-Hant) | Explicit only | Full (zh-Hans + override) | `zh` + `en` |
| Japanese (ja) | Hiragana/Katakana | Full (160+ terms) | `ja` + `en` |
| Korean (ko) | Hangul | Full (160+ terms) | `ko` + `en` |

Auto-detection rules:
- Hangul Syllables (U+AC00–U+D7AF) → `ko`
- Hiragana (U+3040–U+309F) or Katakana (U+30A0–U+30FF) → `ja`
- CJK characters → `zh-Hans`
- Otherwise → `en-US`

## Compliance Notes

- For CC BY scenarios, render `open_meteo_compliance_notice` in a visible area when `source=open-meteo`.
- Do not silently drop `open_meteo_compliance_notice` when Open-Meteo is the actual source.
- `source` and `source_display` are useful for traceability and UI, but they do not replace `open_meteo_compliance_notice`.
- `rate_limit_notice` is returned only when Open-Meteo fails and fallback is activated.

## Open-Meteo and wttr.in Notes

Open-Meteo:

- Supports Chinese, Japanese, and Korean geocoding input.
- Weather condition text is translated in plugin logic.
- Forecast response is numeric and weather-code based.

wttr.in:

- Supports Unicode locations.
- Can provide localized weather descriptions.

References:

- Open-Meteo Geocoding API: https://open-meteo.com/en/docs/geocoding-api
- Open-Meteo Forecast API: https://open-meteo.com/en/docs
- Open-Meteo License: https://open-meteo.com/en/licence
- Open-Meteo Terms: https://open-meteo.com/en/terms
- wttr.in Help: https://wttr.in/:help
- wttr.in Repository: https://github.com/chubin/wttr.in

## Support

- GitHub profile: https://github.com/AlexMultiAgent
- GitHub Issues: https://github.com/AlexMultiAgent/dify-plugin-myweather/issues

## License

MIT License. See [LICENSE](./LICENSE).
