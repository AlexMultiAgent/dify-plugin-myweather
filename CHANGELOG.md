# Changelog

All notable changes to MyWeather are documented in this file. The newest release
is listed first.

## 0.1.5 - 2026-11-23

### Changed

- No runtime changes. The plugin code, runtime dependencies, and request/response
  behavior are identical to 0.1.4; this release carries the supply-chain hardening
  built since then.
- Every GitHub Action is pinned by commit SHA, and Dependabot keeps those pins and
  the development toolchain current.
- Tagged releases now attach a Sigstore build-provenance bundle next to the
  `.difypkg`.

### Added

- CodeQL static analysis and OpenSSF Scorecard supply-chain scanning in CI.
- `SECURITY.md` vulnerability-reporting policy and a `.github/CODEOWNERS` file.

## 0.1.4 - 2026-11-18

### Fixed

- Chinese county, district, township, and village names no longer resolve through
  wttr.in aliases or neighboring jurisdictions.
- Ambiguous Japanese Han names now use Japanese geocoding and Japan-first filtering
  when `language=ja` is selected.
- Open-Meteo candidates without a meaningful name match are rejected instead of
  returning an unrelated place.
- Provider-wide HTTP failures stop candidate fan-out to avoid retry amplification.
- Chinese administrative suffixes are normalized when the requested output language
  is English or another non-CJK language.
- Runtime dependencies now resolve through the plugin daemon's package mirror, and
  local Playwright artifacts are excluded from distribution packages.

### Added

- Runtime `.difypkg` verification in CI and a reusable package verification script.
- Release-tag validation and automated GitHub Release assets for tagged versions.
- Regression coverage for mainland/Taiwan alias collisions and Japanese city names.

## 0.1.3 - 2026-11-17

### Fixed

- Hardened malformed-response fallback, bounded lookup deadlines, and native-script
  place resolution.
- Aligned package contents, runtime requirements, and Marketplace metadata.
