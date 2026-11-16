# Marketplace Pre-Submit Checklist

Check each item before submitting to the Dify Marketplace.

## Manifest

- [ ] Before choosing a version, check the latest official package under
  `langgenius/dify-plugins/AlexMultiAgent/myweather` and increment from that
  published version. Local, unpublished `.difypkg` versions are not release baselines.
- [ ] `manifest.yaml` version matches the packaged `.difypkg` version AND the `USER_AGENT` string in `tools/weather_logic.py`
- [ ] `author` field is consistent across `manifest.yaml`, `provider/myweather.yaml`, and `tools/weather_lookup.yaml`
- [ ] `created_at` reflects the initial publish date (`2026-04-08T00:00:00Z`)
- [ ] `icon` points to `icon.svg`
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

`dify plugin package` archives every file in the target directory — it ignores `.gitignore` and
does not honour `.difypkgignore` — so stage a runtime-only copy before packaging.

```bash
STAGE=../myweather-stage
rm -rf "$STAGE" && mkdir -p "$STAGE"
cp manifest.yaml main.py requirements.txt pyproject.toml icon.svg README.md LICENSE PRIVACY.md "$STAGE/"
cp -r _assets provider tools "$STAGE/"
find "$STAGE" -name '__pycache__' -type d -prune -exec rm -rf {} +
cd .. && dify plugin package myweather-stage
```

- [ ] Packaging command succeeds without errors
- [ ] Generated `.difypkg` includes `manifest.yaml`, `main.py`, `requirements.txt`, `provider/`, `tools/`, and `_assets/icon.svg`
- [ ] Generated `.difypkg` excludes `.git/`, `tests/`, `.env*`, `__pycache__/`, and local agent/tool directories
- [ ] Plugin installs and runs in a Dify instance

## Functional

- [ ] `open-meteo` primary source works for English and CJK locations
- [ ] `wttr` primary source works for English and Chinese locations
- [ ] Fallback triggers correctly when the primary source fails
- [ ] Fallback triggers when Open-Meteo geocoding returns no match and `rate_limit_notice` is set
- [ ] Language auto-detection works for Korean (Hangul), Japanese (kana), Chinese (CJK)
- [ ] Taiwan / Hong Kong / Macau place names resolve to Traditional Chinese
- [ ] Explicit language selection overrides auto-detection
- [ ] `uscs` unit selection shows Fahrenheit and mph
- [ ] `include_raw_json` adds a `raw` key and no keys absent from `output_schema`

## Place Name Resolution

The reported `location` has to name the place the provider actually matched, not the
raw query — a wrong match must never hide behind the user's own wording.

- [ ] `서울` resolves to Seoul, not to a same-sounding village
- [ ] `부산` resolves to Busan
- [ ] `とうきょう` resolves to Tokyo, not to an unrelated district
- [ ] `横浜` resolves to 横浜市 (神奈川県), not to a hamlet in another prefecture
- [ ] `台北` resolves to Taipei
- [ ] `深圳` resolves to Shenzhen, not to Hong Kong
- [ ] `北京` resolves to 北京 (北京市)
