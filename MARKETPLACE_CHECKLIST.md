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
- [ ] `repo` is the source repository on an allowed host (github.com, gitlab.com, …)
- [ ] `contact` is a reachable address — the Marketplace requires it, so use the
      GitHub noreply address rather than a personal mailbox
- [ ] `network.domains` lists every host the plugin actually calls
      (`wttr.in`, `api.open-meteo.com`, `geocoding-api.open-meteo.com`)

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

## README

- [ ] `README.md` primary content is English — localized prose and CJK examples
      belong in `readme/README_zh_Hans.md`, which is the path and name the
      Marketplace reads for a translated README
- [ ] `README.md` states the connection requirements (the hosts the plugin calls)
- [ ] `README.md` links the source repository on an allowed host
- [ ] No personal email address in the README or the manifest

## Packaging

`dify plugin package` honours `.difyignore`, which keeps the development files out
of the package. The CLI refuses `.` as an input path and names the output after the
input directory, so the output path is given explicitly:

```bash
cd ..
dify plugin package dify-plugin-myweather -o myweather-0.1.3.difypkg
```

`.difyignore` is the only filter — `.gitignore` is ignored — so it has to name
`.env`, `.playwright-mcp/`, `tests/`, `docs/`, `__pycache__/` and the built
package itself. Check the contents of the result before submitting it:

```bash
python -c "import zipfile;print(sorted(zipfile.ZipFile('myweather-0.1.3.difypkg').namelist()))"
```

- [ ] Packaging command succeeds without errors
- [ ] Generated `.difypkg` includes `manifest.yaml`, `main.py`, `requirements.txt`, `provider/`, `tools/`, `readme/`, and `_assets/icon.svg`
- [ ] Generated `.difypkg` excludes `.git/`, `tests/`, `.env*`, `__pycache__/`, and local agent/tool directories
- [ ] Plugin installs and runs in a Dify instance

## Static Analysis & Dependencies

```bash
uv sync --group dev
ruff check .
ruff format --check .
pyright --project pyproject.toml
pip-audit -r requirements.txt
```

- [ ] `ruff check .` passes with the rule set pinned in `pyproject.toml`
- [ ] `ruff format --check .` reports every file already formatted
- [ ] `pyright --project pyproject.toml` reports zero errors
- [ ] `pip-audit -r requirements.txt` reports no known vulnerabilities

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
- [ ] A malformed upstream payload falls back to the other provider instead of raising
- [ ] The lookup gives up on the second provider once the lookup deadline is reached
- [ ] At most four location candidates are queried per provider
- [ ] A failing lookup still emits every declared output variable, with `null` for the numeric ones

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
