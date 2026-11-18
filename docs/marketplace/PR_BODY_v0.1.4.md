# Plugin Submission

## Plugin information

- **Author**: AlexMultiAgent
- **Plugin name**: myweather
- **Version**: 0.1.4
- **Source repository**: https://github.com/AlexMultiAgent/dify-plugin-myweather
- **Contact**: AlexMultiAgent@users.noreply.github.com

## Submission type

- [ ] New plugin
- [x] Version update

## What changed

- Corrected ambiguous mainland/Taiwan alias handling and Chinese county/district
  resolution.
- Added reliable Japanese Han-name resolution when `language=ja` is selected.
- Rejected weak Open-Meteo candidates and stopped provider-wide retry fan-out.
- Added runtime package verification and automated tagged GitHub Releases.

## Risk level

- [ ] Low risk
- [x] Medium risk
- [ ] High risk

The plugin sends the user-entered place name to fixed Open-Meteo and wttr.in HTTPS
endpoints. It does not request device geolocation, execute code or commands, access
files, proxy arbitrary URLs, or perform write actions in third-party services.

## Required checks

- [x] I have read and followed the Marketplace submission requirements.
- [x] I have read and comply with the Plugin Development Guidelines.
- [ ] I tested this plugin on Dify Community Edition and Dify Cloud, or documented
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
pytest: 255 passed
ruff check: passed
ruff format --check: 22 files already formatted
pyright: 0 errors, 0 warnings
pip-audit: no known vulnerabilities
package verification: 19 runtime entries verified
```

Live upstream smoke tests after the fix resolved an ambiguous mainland Chinese county
and four Japanese Han-only city names to their intended locations. The package was
also downloaded from the GitHub Release and re-verified against the tagged source
tree.

## Reviewer notes

This is a version-update PR and contains only:

```text
AlexMultiAgent/myweather/myweather-0.1.4.difypkg
```

Release asset:

```text
https://github.com/AlexMultiAgent/dify-plugin-myweather/releases/download/v0.1.4/myweather-0.1.4.difypkg
```

Package SHA-256:

```text
11335bcee3210fe535e51f481ce9cba13e526cd82dc9890a162dbd62dcef1b19
```

A fresh Dify Community/Cloud installation was not repeated for 0.1.4. The manifest,
tool parameters, output schema, dependencies, and installation surface are unchanged
from 0.1.3, which passed the Marketplace review and was exercised in Dify Community
Edition 1.19.0. This update changes location-resolution logic and release tooling.
