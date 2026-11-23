# Plugin Submission

## Plugin information

- **Author**: AlexMultiAgent
- **Plugin name**: myweather
- **Version**: 0.1.5
- **Source repository**: https://github.com/AlexMultiAgent/dify-plugin-myweather
- **Contact**: AlexMultiAgent@users.noreply.github.com

## Submission type

- [ ] New plugin
- [x] Version update

## What changed

- No runtime changes: the plugin code, runtime dependencies, and request/response
  behavior are identical to 0.1.4.
- Added CodeQL static analysis and OpenSSF Scorecard supply-chain scanning to CI.
- Pinned every GitHub Action by commit SHA and enabled Dependabot for the action
  pins and the development toolchain.
- Added `SECURITY.md` and `.github/CODEOWNERS`.
- Tagged releases now attach a Sigstore build-provenance bundle next to the
  `.difypkg`.

## Risk level

- [ ] Low risk
- [x] Medium risk
- [ ] High risk

The plugin sends the user-entered place name to fixed Open-Meteo and wttr.in HTTPS
endpoints. It does not request device geolocation, execute code or commands, access
files, proxy arbitrary URLs, or perform write actions in third-party services. No
runtime code changed in this version.

## Required checks

- [x] I have read and followed the Marketplace submission requirements.
- [x] I have read and comply with the Plugin Development Guidelines.
- [x] I tested this plugin on Dify Community Edition and Dify Cloud, or documented
      any limitation below.
- [x] The package contains only files needed at runtime.
- [x] The package does not contain secrets, local credentials, `.env` files, `.git`
      directories, virtual environments, caches, logs, or IDE files.
- [x] The package does not contain executables or bundled binaries.
- [x] The plugin README includes setup steps, usage instructions, connection
      requirements, and the source repository link.
- [x] The plugin includes `PRIVACY.md`, and `manifest.yaml` references it.
- [x] User-facing text is primarily English, with localized CJK documentation
      following Dify's multilingual README guidance.

## Security and privacy notes

The plugin requires no credentials. It sends only the submitted place name to the
three domains declared in `manifest.yaml`. Queries and responses are not persisted by
the plugin. Routine plugin logs omit raw location text.

## Local validation

```text
pytest: 256 passed
ruff check: passed
ruff format --check: 24 files already formatted
pyright: 0 errors, 0 warnings
pip-audit: no known vulnerabilities
package verification: 19 runtime entries verified
Dify Community Edition 1.20.0 local package install: passed
```

The package attached to the GitHub Release was downloaded and re-verified against
the tagged source tree. It is byte-identical to the local build (SHA-256
`c1e35452b03819dab11706ba9c1b404c4e14e90014a21cd4ff06a7e8d295cb82`), and its build
provenance was verified with `gh attestation verify`.

Dify Community Edition 1.20.0 was upgraded from 0.1.4 to 0.1.5 through the package
upload API and listed the installed version as 0.1.5. A live invocation with
`location=台北` and `language=zh-Hant` returned Traditional Chinese output
(`溫度 24.0°C，體感 25.0°C，濕度 67%，風速 5.0 公里/小時`). Open-Meteo was unreachable
from that local sandbox during the check, and the plugin fell back to wttr.in as
designed. Dify Cloud was not exercised from this local environment.

## Reviewer notes

This is a version-update PR and contains only:

```text
AlexMultiAgent/myweather/myweather-0.1.5.difypkg
```

Release asset:

```text
https://github.com/AlexMultiAgent/dify-plugin-myweather/releases/download/v0.1.5/myweather-0.1.5.difypkg
```

Package SHA-256:

```text
c1e35452b03819dab11706ba9c1b404c4e14e90014a21cd4ff06a7e8d295cb82
```

Compared with 0.1.4, only four packaged files differ: `README.md` (Scorecard badge)
and the version strings in `manifest.yaml`, `pyproject.toml`, and
`tools/weather_logic.py`. The 0.1.5 release also carries a signed build-provenance
bundle (`myweather-0.1.5.sigstore.json`) as a GitHub Release asset.
