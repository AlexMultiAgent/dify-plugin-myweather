# MyWeather

Dify weather plugin. No API key; wttr.in + Open-Meteo; output in English,
Simplified Chinese, Traditional Chinese, Japanese and Korean.

## Commands

```bash
# the four CI gates -- `uv run` matches CI exactly
uv run pytest -q                                               # 256 tests, ~30s
uv run ruff check . && uv run ruff format --check .            # lint + format (rule set pinned in pyproject.toml)
uv run pyright                                                 # type gate
uv run pip-audit --no-deps --disable-pip -r requirements.txt   # dependency audit

# package: build from the parent with -o, then verify the runtime contents
cd .. && dify plugin package dify-plugin-myweather -o "dify-plugin-myweather/myweather-0.1.5.difypkg"
uv run python scripts/verify_package.py myweather-0.1.5.difypkg --source-root .
dify plugin run myweather-0.1.5.difypkg -l    # smoke-test a package locally

# marketplace validation -- the bar is 0 blocking failures
git clone --depth 1 https://github.com/langgenius/dify-marketplace-toolkit /tmp/dify-marketplace-toolkit
python /tmp/dify-marketplace-toolkit/validator/validate-difypkg.py myweather-0.1.5.difypkg --pr-body-file docs/marketplace/PR_BODY_v0.1.5.md
```

The executable-permission warning the validator prints on every file is a Windows
host artifact (`os.access(X_OK)` is true for any existing file there); CI runs on
Linux and does not report it.

The lint/type/audit tools are dev dependencies: `uv sync --locked --group dev`.
`uv run pyright` resolves the project interpreter on its own; a standalone
`pyright` needs `--pythonpath <python>` or it reports every third-party import
as missing.

## Layout

| Path | Role |
| --- | --- |
| `manifest.yaml` | plugin identity; drives the marketplace listing |
| `main.py` | the entry point named by `manifest.yaml` |
| `.difyignore` | the only filter `dify plugin package` honours |
| `README.md` | the English README the Marketplace shows (it must stay English) |
| `readme/README_zh_Hans.md` | the Chinese README — the path the Marketplace reads |
| `provider/myweather.yaml` · `provider/myweather.py` | tool provider (no credentials) |
| `tools/weather_lookup.yaml` | tool, parameter and `output_schema` declaration |
| `tools/weather_lookup.py` | the `Tool` subclass; emits variables + JSON + text |
| `tools/weather_logic.py` | all the real work: fetching, geocoding, formatting |
| `tools/transliteration.py` | Hangul/Kana romanizers, place-name variants |
| `tools/translations.py` | 146 weather-condition terms × 4 languages |
| `scripts/verify_package.py` | the runtime-package contract CI enforces |
| `tests/` | 4 modules; the logic layer, transliteration, config and packaging |
| `.github/workflows/ci.yml` | the gates, plus tag → GitHub Release |
| `MARKETPLACE_CHECKLIST.md` | pre-submit checklist |
| `docs/marketplace/` | release flow + the PR body for the current version |

`tools/weather_logic.py` is the unit under test; `tools/weather_lookup.py` is a
thin adapter over it.

## Gotchas

**Packaging.** `dify plugin package` honours `.difyignore` in the plugin directory
and ignores `.gitignore`; it refuses `.` as the input path and names the output
after the input directory, so build it from the parent with `-o`. `.difyignore` is
the only filter — a rule missing there leaks into the package (an earlier build
shipped the whole `.git/` directory, a later one shipped `.env`, and Playwright's
`output/` directory has to be named there too).

**`scripts/verify_package.py` is the package contract.** It requires the 19 runtime
files, rejects dev-only files and directories, and compares every packaged file
byte-for-byte against the source root. Run it after every build — a `.difyignore`
slip fails there instead of in the Marketplace.

**Version lives in four places** and must agree: `manifest.yaml` `version`,
`manifest.yaml` `meta.version`, `pyproject.toml` `version`, and `USER_AGENT`
in `tools/weather_logic.py`. CI reads `pyproject.toml` for the package name and
for the `vX.Y.Z` tag check, so the tag has to equal that version.

**Never show the raw query as the location.** `location` and `summary` must
name the place the provider actually matched; showing the query once hid a
provider that answered `서울` with a village 200 km away.

**wttr.in cannot resolve native-script Japanese or Korean.** It returns a
same-sounding neighbourhood (`서울` → Ryongsan, `とうきょう` → Takehiracho),
so those inputs always go through Open-Meteo whatever `source_preference` says.
Japanese *kanji* names are excluded from wttr.in as well.

**The lookup is bounded on purpose.** `TOTAL_LOOKUP_TIMEOUT = 90` (the Dify
runner allows 120) and `MAX_LOCATION_CANDIDATES = 4` cap the fan-out. A
deadline hit raises `WeatherLookupTimeout` instead of starting the next
provider — do not "fix" that by falling through.

**The geocoder's `language` must follow the query's script.** A Latin query
has to be asked for with `language=en`; otherwise the scorer compares it
against localized names and picks the wrong place (`seoul` → *Seoullaendeu*).

**`WeatherLookupError` derives from `RuntimeError`.** It has to be in the
`except` tuple in `get_weather`, or a geocoding miss escapes the
source-fallback loop and fails the lookup instead of falling back.

**`requirements.txt` must ship inside the `.difypkg`** — the plugin daemon
installs the plugin's dependencies from it, and it resolves them through the
daemon's own package mirror, which lags PyPI. A release that exists on PyPI
can still fail to install there, which is why `regex` is pinned to `2026.9.29`
in `pyproject.toml`. Nothing in `tools/` imports `regex` — do **not** "clean up"
that dependency, it is a mirror-compatibility pin. Regenerate the lockfile and
the export together:

```bash
uv lock && uv export --format requirements-txt --no-hashes --no-dev --no-emit-project --output-file requirements.txt
```

**Open-Meteo is CC BY 4.0.** Render `open_meteo_compliance_notice` whenever
`source=open-meteo`.

## Testing

Tests mock `requests.Session.request`, so no network is used. Two entry
points: `_build_mock_session()` in `tests/test_weather_logic.py` for the logic
layer, and `WeatherLookupTool.from_credentials({})` + `.invoke(params)` for
the tool layer.

The suite runs against the SDK in `.venv`; the plugin declares `>=0.9.0,<1.0.0`.

## End-to-end test in the local Dify

The simplest path is the UI: **Integrations → Install → Local Package File**
uploads the `.difypkg` and upgrades the existing installation in place. Use it
to confirm the package installs and the tool's parameters render.

The plugin daemon's HTTP API is only reachable inside the docker network, so the
calls run **inside the api container**. The local instance's tenant id, the
container names and the key locations are in `CLAUDE.local.md`, which is not
checked in.

```bash
# The local instance's paths and container names live in CLAUDE.local.md.
docker cp myweather-<version>.difypkg <api-container>:/tmp/pkg.difypkg
docker exec -i <api-container> python - < install_and_invoke.py   # throwaway script, not in the repo
```

| Call | Route |
| --- | --- |
| installed plugins | `GET /plugin/<tid>/management/list?page=1&page_size=256&response_type=paged` |
| uninstall | `POST /plugin/<tid>/management/uninstall` — `{"plugin_installation_id": id}` |
| upload | `POST /plugin/<tid>/management/install/upload/package` — multipart `dify_pkg`, `verify_signature=false` |
| install | `POST /plugin/<tid>/management/install/identifiers` — `{"plugin_unique_identifiers": [id], "source": "package", "metas": [...]}` |
| task | `GET /plugin/<tid>/management/install/tasks/<task_id>` |
| invoke | `POST /plugin/<tid>/dispatch/tool/invoke` — header `X-Plugin-ID: alexmultiagent/myweather` |

Two things that cost time to find: the daemon answers `{"code":0,"data":{...}}`, so
an SSE parser has to unwrap one more level to reach the message, and the
`credential_type` of a tool without credentials is `unauthorized`, not `secret`.
The upload response carries the identifier under `unique_identifier`.

## Before publishing

`MARKETPLACE_CHECKLIST.md` is the pre-submit checklist, and
`docs/marketplace/README.md` is the release flow: tag `vX.Y.Z` → CI builds,
verifies and publishes a GitHub Release → copy the `.difypkg` into
`langgenius/dify-plugins` under `AlexMultiAgent/myweather/` → open the
Marketplace PR with `docs/marketplace/PR_BODY_v<version>.md` as the body.
The plugin reaches the debug daemon through `.env` (`REMOTE_INSTALL_URL` /
`REMOTE_INSTALL_KEY`); `.env` is gitignored, `.env.example` is not.

**The version baseline is what is published, not what is built here.** The next
version is the one after the latest `.difypkg` under
`langgenius/dify-plugins/AlexMultiAgent/myweather`; a local build that was never
submitted does not count. `0.1.4` is published (Marketplace PR merged
2026-11-18), so the next version is `0.1.5`.

**Three things block a submission** (the rest are warnings): the manifest needs a
top-level `repo` (a URL on github.com) and a top-level `contact` (an email); the
root `README.md` must be English, since CJK outside a fenced code block is
rejected; a translation belongs in `readme/README_<locale>.md`.
