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
pytest: 254 passed
ruff check: passed
ruff format --check: 22 files already formatted
pyright: 0 errors, 0 warnings
pip-audit: no known vulnerabilities
package verification: 19 runtime entries verified
```

## Reviewer notes

This is a version-update PR and contains only:

```text
AlexMultiAgent/myweather/myweather-0.1.4.difypkg
```

Package SHA-256:

```text
fbe203d107aad3b8d12431420b697759ff3e35fc3721ca1b5325e1537858a69f
```
