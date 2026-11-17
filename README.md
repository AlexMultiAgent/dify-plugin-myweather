# MyWeather

MyWeather is a Dify weather plugin that requires no API key.

- Primary source is selectable: `open-meteo` or `wttr`
- Default primary source: `open-meteo`
- The non-primary source is normally used as fallback; native-script Japanese and Korean names are Open-Meteo-only
- Supports English, Simplified Chinese, Traditional Chinese, Japanese, and Korean input and output
- Automatic language detection via Unicode scripts and a bounded place-name hint table
- Native-script Japanese and Korean place names are transliterated before geocoding

## Example Output

**English** (input: `London`)

> London, England, United Kingdom: Partly cloudy. Temp 12.0 °C, feels like 10.5 °C, humidity 72%, wind 11.0 km/h.

**Korean** (input: the Hangul name of Seoul)

```text
Seoul, South Korea: 구름많음. 기온 12.6°C, 체감 10.1°C, 습도 61%, 풍속 7.0 km/h.
```

**Japanese** (input: the kanji name of Yokohama)

```text
横浜市, 神奈川県, 日本：曇り。気温 15.5°C、体感 12.5°C、湿度 51%、風速 9.0 km/h。
```

Workflow: `Start (city) → Weather Lookup → Output`

## Quick Start

1. Install plugin `MyWeather` in Dify.
2. Add tool node `Weather Lookup`.
3. Set `source_preference`:
   - `open-meteo` (default): Open-Meteo first, wttr fallback for supported scripts
   - `wttr`: wttr first, Open-Meteo fallback
   - Native-script Japanese and Korean names always use Open-Meteo directly
4. Pass user location text to `location`.

## Connection Requirements

The plugin makes outbound HTTPS requests to three hosts and needs no API key,
account, token, or other credential:

| Host | Purpose |
| --- | --- |
| `api.open-meteo.com` | Open-Meteo forecast endpoint |
| `geocoding-api.open-meteo.com` | Open-Meteo place-name lookup |
| `wttr.in` | Fallback weather source |

If the Dify deployment restricts outbound traffic, allow these three hosts.
Only the place name the user typed is sent; see [PRIVACY.md](./PRIVACY.md).

## Tool Parameters

- `location` (required): city, region, airport code, or place name. Supports English, Chinese, Japanese, and Korean.
- `location` is limited to 200 characters to keep upstream requests and logs bounded.
- `language` (optional): output language. `auto` (default) detects from input — Hangul → Korean, hiragana/katakana → Japanese, recognized Taiwan / Hong Kong / Macau / Japan place names → their regional language, other CJK → Simplified Chinese, otherwise English. Set it explicitly for ambiguous Han-only names. Supported explicit values are `en-US`, `zh-Hans`, `zh-Hant`, `ja`, and `ko`.
- `units` (optional): `metric` or `uscs`.
- `source_preference` (optional): `open-meteo` (default) or `wttr`.
- `include_raw_json` (optional): include the raw upstream provider payload in the JSON output, under the `raw` key.

## Output Variables

Returned by `weather_lookup`:

- `source`: actual provider used (`wttr` or `open-meteo`).
- `source_display`: UI-ready source label (`Source: wttr.in.` or `Source: Open-Meteo.`).
- `language`: resolved output language (`en-US`, `zh-Hans`, `zh-Hant`, `ja`, or `ko`).
- `location`: the place the provider actually matched, not the raw query.
- `condition`: weather condition text (translated when CJK/Japanese output).
- `temperature`: current temperature in selected units.
- `temperature_unit`: `°C` or `°F`.
- `feels_like`: feels-like temperature.
- `humidity`: relative humidity percentage.
- `wind_speed`: wind speed in selected units.
- `wind_speed_unit`: `km/h` or `mph`.
- `summary`: concise weather sentence without inline source text (localized).
- `open_meteo_compliance_notice`: Open-Meteo attribution plus modification declaration (only when source is Open-Meteo).
- `rate_limit_notice`: fallback notice (only when Open-Meteo fails, including HTTP 429, and fallback is triggered).

The default text message appends `source_display` and, when applicable,
`open_meteo_compliance_notice`, so workflows that only consume the text message
still show the actual provider and required attribution.

## Language Support

| Language | Detection | Weather Translation | Geocoding |
| --- | --- | --- | --- |
| English (en-US) | Default | Passthrough | Standard |
| Simplified Chinese (zh-Hans) | CJK characters | Full (146 terms) | Native names |
| Traditional Chinese (zh-Hant) | Recognized TW / HK / MO names | Full (zh-Hans + override) | Latin aliases |
| Japanese (ja) | Hiragana/Katakana or recognized Japanese Han names | Full (146 terms) | Hepburn + suffix variants |
| Korean (ko) | Hangul | Full (146 terms) | Revised Romanization |

Auto-detection rules:

- Hangul Syllables (U+AC00–U+D7AF) → `ko`
- Hiragana (U+3040–U+309F) or Katakana (U+30A0–U+30FF) → `ja`
- CJK characters → `zh-Hans`, unless the text names a recognized Taiwan / Hong Kong / Macau / Japan place
- Otherwise → `en-US`

Han-only place names can be identical across languages. Automatic detection uses a
bounded alias table for common regions and cities; set `language` explicitly when
the same Han name is ambiguous in context.

## Place Name Resolution

Both providers index place names in Latin script, and neither handles native-script
Japanese or Korean names on its own — so the plugin transliterates the query before
geocoding it:

| Input script | Transliterated to | How |
| --- | --- | --- |
| Hangul | `seoul`, `busan` | Revised Romanization; the administrative suffix (`수원시` → `suwon`) is dropped |
| Kana | `tokyo`, `sapporo` | Hepburn |
| Japanese kanji | `Yokohama-shi`, `Yokohama-to` | Administrative-suffix variants, because the bare name can match an unrelated hamlet in another prefecture |
| Chinese | — | Already indexed natively, so the query is passed through |
| Taiwan / Hong Kong / Macau | `Taipei`, `Hong Kong` | The upstream index stores these under their English names |

Worked examples:

```text
서울      -> seoul
부산      -> busan
수원시    -> suwon
とうきょう -> tokyo
さっぽろ  -> sapporo
横浜      -> 横浜市, 横浜都
北京      -> (native, no transliteration needed)
台北      -> Taipei
```

Both romanizers are deterministic — Unicode syllable decomposition for Hangul, a fixed
table for kana — so no phonetic dictionary ships with the plugin and there is nothing
to maintain. The one lookup table is the administrative divisions of Taiwan, Hong Kong
and Macau, which changes very rarely.

wttr.in cannot resolve native-script Japanese or Korean names at all: it answers the
Hangul name of Seoul with a village called Ryongsan, and the kana name of Tokyo with a
district called Takehiracho. Those inputs are therefore always resolved through
Open-Meteo, whatever `source_preference` says, and the reported `location` always
names the place the provider actually matched.

## Open-Meteo and wttr.in Notes

Open-Meteo:

- Resolves Chinese place names natively, and Japanese and Korean names once transliterated.
- Its localized index is not complete, so the plugin also tries the native-script name.
- When geocoding finds no match the plugin falls back to wttr.in and sets `rate_limit_notice`, except for native-script Japanese and Korean names.
- Weather condition text is translated in plugin logic.
- Forecast response is numeric and weather-code based.

wttr.in:

- Resolves Latin-script and Chinese place names, but maps Japanese and Korean names to a
  nearby feature instead of the city, so it is not used for native-script Japanese or Korean.
- Can provide localized weather descriptions.
- A wttr.in result is rejected when its country conflicts with a recognized
  regional hint, or when a Han-only query that defaults to Simplified Chinese is
  matched to Hong Kong, Macau, or Taiwan. The plugin then tries the next
  candidate or reports failure rather than silently returning the wrong city.

## Development Checks

Runtime dependencies in `requirements.txt` are exported from `uv.lock` with exact
versions. CI runs the same checks on every push and pull request:

```bash
uv sync --locked --group dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pip-audit --no-deps --disable-pip -r requirements.txt
```

The plugin itself does not log raw location text, including at debug level.

References:

- Open-Meteo Geocoding API: https://open-meteo.com/en/docs/geocoding-api
- Open-Meteo Forecast API: https://open-meteo.com/en/docs
- Open-Meteo License: https://open-meteo.com/en/licence
- Open-Meteo Terms: https://open-meteo.com/en/terms
- wttr.in Help: https://wttr.in/:help
- wttr.in Repository: https://github.com/chubin/wttr.in

## Support

- Source repository: https://github.com/AlexMultiAgent/dify-plugin-myweather
- GitHub profile: https://github.com/AlexMultiAgent
- GitHub Issues: https://github.com/AlexMultiAgent/dify-plugin-myweather/issues

## License

MIT License. See [LICENSE](./LICENSE).

For the Simplified Chinese version of this document, see
[readme/README_zh_Hans.md](./readme/README_zh_Hans.md).
