# MyWeather Comprehensive Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Fix the reliability, fallback, place-detection, output-contract, documentation, and package-consistency issues found during the comprehensive review.

**Architecture:** Keep the existing thin Dify tool adapter and centralize all fetch/geocode/format behavior in `tools/weather_logic.py`. Add a global lookup deadline and bounded candidate fan-out around the existing source fallback, validate upstream response shape through the existing per-candidate exception boundary, and share place aliases from `tools/transliteration.py` when inferring language/country hints. Keep the public tool parameters and output fields unchanged, except for declaring failure-safe numeric output fields nullable.

**Tech Stack:** Python 3.12, Dify Plugin SDK, requests, pytest, Pyright, Ruff

**Spec:** This plan implements the validated findings in the 2026-11-16 comprehensive project review. The canonical inputs are the current `README.md`, `MARKETPLACE_CHECKLIST.md`, `manifest.yaml`, `tools/weather_logic.py`, `tools/transliteration.py`, `tools/weather_lookup.py`, and `tools/weather_lookup.yaml`.

## Global Constraints

- Keep all third-party destinations fixed to `https://wttr.in` and Open-Meteo HTTPS endpoints.
- Keep the lookup within the Dify runner's 120-second `MAX_REQUEST_TIMEOUT`.
- Preserve Open-Meteo attribution behavior for every successful Open-Meteo result.
- Preserve native-script Korean and kana placement on Open-Meteo only.
- Keep the public parameter names and emitted output field names unchanged.
- Bump the patch version from the official `0.1.2` release to `0.1.3` in `manifest.yaml`, `pyproject.toml`, and `USER_AGENT`.
- Do not include tests, local agent files, caches, or environment files in the generated `.difypkg`.

---

### Task 1: Make malformed upstream responses enter source fallback

**Files:**
- Modify: `tools/weather_logic.py`
- Test: `tests/test_weather_logic.py`

**Interfaces:**
- Consumes: `get_weather(location, units="metric", preferred_source="open-meteo", language="auto", session=None)`
- Produces: malformed JSON object shapes raise no uncaught `AttributeError` or `IndexError`; they become ordinary source failures and allow the next provider to run.

- [x] **Step 1: Write the failing fallback tests**

```python
def test_get_weather_wttr_malformed_payload_falls_back_to_open_meteo():
    session = Mock(spec=requests.Session)

    def response(body):
        resp = Mock(spec=requests.Response)
        resp.json.return_value = body
        resp.raise_for_status.return_value = None
        return resp

    session.request.side_effect = [
        response({"current_condition": ["bad"]}),
        response(_mock_open_meteo_geocode_response()),
        response(_mock_open_meteo_forecast_response()),
    ]

    result = get_weather("London", preferred_source="wttr", session=session)
    assert result["source"] == "open-meteo"


def test_get_weather_open_meteo_malformed_payload_falls_back_to_wttr():
    session = Mock(spec=requests.Session)

    def response(body):
        resp = Mock(spec=requests.Response)
        resp.json.return_value = body
        resp.raise_for_status.return_value = None
        return resp

    session.request.side_effect = [
        response(["bad"]),
        response(_mock_wttr_response()),
    ]

    result = get_weather("London", preferred_source="open-meteo", session=session)
    assert result["source"] == "wttr"
```

- [x] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_weather_logic.py::test_get_weather_wttr_malformed_payload_falls_back_to_open_meteo tests/test_weather_logic.py::test_get_weather_open_meteo_malformed_payload_falls_back_to_wttr -q`

Expected: both fail with `AttributeError`, proving the exception bypasses fallback.

- [x] **Step 3: Add the minimal exception-boundary fix**

```python
except (
    requests.RequestException,
    WeatherLookupError,
    AttributeError,
    IndexError,
    KeyError,
    TypeError,
    ValueError,
) as exc:
```

- [x] **Step 4: Run tests and verify GREEN**

Run: `python -m pytest tests/test_weather_logic.py -q`

Expected: all weather logic tests pass.

---

### Task 2: Add a global deadline and bound location fan-out

**Files:**
- Modify: `tools/weather_logic.py`
- Test: `tests/test_weather_logic.py`

**Interfaces:**
- Consumes: existing `_retry_request`, `_fetch_from_wttr`, and `_fetch_from_open_meteo`.
- Produces: `WeatherLookupTimeout(WeatherLookupError)`, `TOTAL_LOOKUP_TIMEOUT = 90`, `MAX_LOCATION_CANDIDATES = 4`, deadline-aware request timeouts, and a hard candidate cap.

- [x] **Step 1: Write failing request-budget tests**

```python
def test_get_weather_limits_candidate_fanout(monkeypatch):
    attempted = []

    def fail(open_meteo_query, *_args, **_kwargs):
        attempted.append(open_meteo_query)
        raise WeatherLookupError("no match")

    monkeypatch.setattr("tools.weather_logic._fetch_from_open_meteo", fail)

    with pytest.raises(WeatherLookupError):
        get_weather("a和b和c和d和e和f", preferred_source="open-meteo")

    assert len(attempted) <= MAX_LOCATION_CANDIDATES


def test_get_weather_does_not_start_fallback_after_deadline(monkeypatch):
    calls = []

    def timeout(*_args, **_kwargs):
        calls.append("open-meteo")
        raise WeatherLookupTimeout("deadline exceeded")

    def fallback(*_args, **_kwargs):
        calls.append("wttr")
        return {"source": "wttr"}

    monkeypatch.setattr("tools.weather_logic._fetch_from_open_meteo", timeout)
    monkeypatch.setattr("tools.weather_logic._fetch_from_wttr", fallback)

    with pytest.raises(WeatherLookupError, match="deadline"):
        get_weather("London", preferred_source="open-meteo")

    assert calls == ["open-meteo"]
```

- [x] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_weather_logic.py::test_get_weather_limits_candidate_fanout tests/test_weather_logic.py::test_get_weather_does_not_start_fallback_after_deadline -q`

Expected: the first test finds more than four attempts; the second fails because `WeatherLookupTimeout` does not exist.

- [x] **Step 3: Implement the deadline and candidate cap**

```python
TOTAL_LOOKUP_TIMEOUT = 90
MAX_LOCATION_CANDIDATES = 4


class WeatherLookupTimeout(WeatherLookupError):
    """Raised when the bounded lookup budget is exhausted."""


def _remaining_lookup_time(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise WeatherLookupTimeout("Weather lookup deadline exceeded.")
    return remaining
```

Use `min(DEFAULT_TIMEOUT, _remaining_lookup_time(deadline))` for every request, ensure retry backoff cannot extend beyond the deadline, truncate both candidate lists, and re-raise `WeatherLookupTimeout` instead of trying another provider.

- [x] **Step 4: Run tests and verify GREEN**

Run: `python -m pytest tests/test_weather_logic.py -q`

Expected: all weather logic tests pass without real sleeps or network access.

---

### Task 3: Fix Han place detection and country-hint false positives

**Files:**
- Modify: `tools/transliteration.py`
- Modify: `tools/weather_logic.py`
- Test: `tests/test_transliteration.py`
- Test: `tests/test_weather_logic.py`

**Interfaces:**
- Consumes: `country_place_names(country_code: str) -> tuple[str, ...]` from transliteration.
- Produces: expanded Taiwan/Hong Kong/Macau/Japan Chinese-name recognition and word-bounded Latin country matching.

- [x] **Step 1: Write the failing place-detection tests**

```python
@pytest.mark.parametrize(
    ("place", "expected_language", "expected_hint"),
    [
        ("九龍", "zh-Hant", "HK"),
        ("嘉义", "zh-Hant", "TW"),
        ("岐阜", "ja", "JP"),
        ("別府", "ja", "JP"),
    ],
)
def test_resolve_language_for_supported_han_places(
    place, expected_language, expected_hint
):
    assert _infer_country_hints(place) == [expected_hint]
    assert _resolve_language("auto", place) == expected_language


def test_country_hints_do_not_match_latin_substrings():
    assert _infer_country_hints("Chinatown, San Francisco") == []
    assert _infer_country_hints("Koreatown, Los Angeles") == []
```

- [x] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_transliteration.py tests/test_weather_logic.py -q`

Expected: new Han place tests fail because they default to `zh-Hans`; substring tests fail with `CN`/`KR`.

- [x] **Step 3: Centralize aliases and use word boundaries**

Add aliases for all Taiwan counties/cities, core Hong Kong and Macau names, and a broader set of Japanese prefectures/cities. Expose alias keys through `country_place_names`. Replace raw substring checks such as `"china" in lowered` with `re.search(r"\bchina\b", lowered)`-style checks.

- [x] **Step 4: Run tests and verify GREEN**

Run: `python -m pytest tests/test_transliteration.py tests/test_weather_logic.py -q`

Expected: all transliteration and weather logic tests pass.

---

### Task 4: Align error outputs with the declared schema

**Files:**
- Modify: `tools/weather_lookup.yaml`
- Test: `tests/test_weather_logic.py`

**Interfaces:**
- Consumes: `_empty_result(lang, loc, error_text)` returns `None` for unavailable numeric fields.
- Produces: `temperature`, `feels_like`, `humidity`, and `wind_speed` accept both their numeric type and `null`.

- [x] **Step 1: Write the failing schema test**

```python
@pytest.mark.parametrize(
    "field",
    ["temperature", "feels_like", "humidity", "wind_speed"],
)
def test_numeric_output_fields_allow_null_failures(field):
    schema = _tool_yaml()["output_schema"]["properties"][field]
    assert "null" in schema["type"]
```

- [x] **Step 2: Run test and verify RED**

Run: `python -m pytest tests/test_weather_logic.py::test_numeric_output_fields_allow_null_failures -q`

Expected: fail because each schema uses a single numeric type.

- [x] **Step 3: Declare nullable JSON Schema types**

Use list-valued JSON Schema types such as `["number", "null"]` and `["integer", "null"]`.

- [x] **Step 4: Run test and verify GREEN**

Run: `python -m pytest tests/test_weather_logic.py -q`

Expected: all weather logic tests pass.

---

### Task 5: Synchronize documentation and privacy-conscious logging

**Files:**
- Modify: `README.md`
- Modify: `tools/weather_lookup.yaml`
- Modify: `tools/weather_logic.py`
- Test: `tests/test_weather_logic.py`

**Interfaces:**
- Consumes: the bounded fallback behavior from Tasks 1-3.
- Produces: documentation that states native-script Korean/kana do not use wttr fallback, and routine logs no longer include the raw location query.

- [x] **Step 1: Add a logging behavior test**

```python
def test_fetch_logging_does_not_include_raw_query(caplog):
    session = Mock(spec=requests.Session)
    resp = Mock(spec=requests.Response)
    resp.json.return_value = _mock_wttr_response()
    resp.raise_for_status.return_value = None
    session.request.return_value = resp

    with caplog.at_level(logging.INFO):
        _fetch_from_wttr("Sensitive Place Name", session)

    assert "Sensitive Place Name" not in caplog.text
```

- [x] **Step 2: Run test and verify RED**

Run: `python -m pytest tests/test_weather_logic.py::test_fetch_logging_does_not_include_raw_query -q`

Expected: fail because the current info log includes the raw location.

- [x] **Step 3: Update logging and documentation**

Remove raw queries from routine info logs, retain diagnostics only at debug level, clarify the Open-Meteo-only native-script exception, describe auto-detection as a heuristic, and recommend explicit `language` for ambiguous Han-only names.

- [x] **Step 4: Run test and verify GREEN**

Run: `python -m pytest tests/test_weather_logic.py -q`

Expected: all weather logic tests pass.

---

### Task 6: Clean static-analysis findings and bump version

**Files:**
- Modify: `tests/test_weather_logic.py`
- Modify: `tools/transliteration.py`
- Modify: `tools/weather_logic.py`
- Modify: `manifest.yaml`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: completed behavior from Tasks 1-5.
- Produces: Ruff-clean production code, Pyright-clean source and tests, and a consistent `0.1.3` patch version.

- [x] **Step 1: Run Ruff and Pyright before cleanup**

Run: `ruff check . --output-format concise`

Run: `pyright --project pyproject.toml`

Expected: Ruff reports style findings and Pyright reports the known test-typing findings.

- [x] **Step 2: Apply behavior-preserving cleanup**

Sort imports, combine nested context managers, use `str.removesuffix`, remove the redundant integer cast, replace list-join suggestions where appropriate, and make test mock return types explicit enough for Pyright.

- [x] **Step 3: Bump the patch version consistently**

Set `manifest.yaml` `version` and `meta.version`, `pyproject.toml` `project.version`, and `USER_AGENT` to `0.1.3`.

- [x] **Step 4: Run all static checks**

Run: `ruff check . --output-format concise`

Run: `ruff format --check .`

Run: `pyright --project pyproject.toml`

Expected: Ruff and Pyright exit successfully.

---

### Task 7: Full regression, package, and integrity verification

**Files:**
- Create: `myweather-0.1.3.difypkg`

**Interfaces:**
- Consumes: the final `0.1.3` source tree.
- Produces: a runtime-only `0.1.3` archive with the same manifest, provider, tool, assets, license, privacy, requirements, and README as the tested source.

- [x] **Step 1: Run the full suite**

Run: `python -m pytest -q`

Expected: zero failures.

- [x] **Step 2: Run compilation and manifest validation**

Run: `python -m compileall -q main.py provider tools tests`

Validate `manifest.yaml` with `PluginConfiguration`.

- [x] **Step 3: Build a runtime-only package**

Stage only `manifest.yaml`, `main.py`, `requirements.txt`, `pyproject.toml`, `icon.svg`, `README.md`, `LICENSE`, `PRIVACY.md`, `_assets/`, `provider/`, and `tools/`; remove caches; archive as `myweather-0.1.3.difypkg`.

- [x] **Step 4: Verify package content**

Assert CRC integrity, version agreement, source-file hashes, and absence of `.git`, `.env`, tests, caches, `.claude`, and `.remember`.

- [x] **Step 5: Run dependency audit**

Run: `pip-audit -r requirements.txt`

Expected: no known vulnerabilities.
