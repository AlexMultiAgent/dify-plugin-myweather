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
- Compared with 0.1.3, the plugin icon now uses refined ring joins and improved
  small-size legibility. [Before](https://github.com/AlexMultiAgent/dify-plugin-myweather/blob/v0.1.3/icon.svg)
  / [After](https://github.com/AlexMultiAgent/dify-plugin-myweather/blob/v0.1.4/icon.svg).

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
pytest: 255 passed
ruff check: passed
ruff format --check: 22 files already formatted
pyright: 0 errors, 0 warnings
pip-audit: no known vulnerabilities
package verification: 19 runtime entries verified
Dify Community Edition 1.19.0 local package upload: passed
```

Live upstream smoke tests after the fix resolved an ambiguous mainland Chinese county
and four Japanese Han-only city names to their intended locations. The package was
also downloaded from the GitHub Release and re-verified against the tagged source
tree.

The package was installed through Dify's **Integrations → Install → Local Package
File** flow. Dify upgraded the existing 0.1.3 installation to 0.1.4, listed the
plugin as a Local Plugin, exposed one `Weather Lookup` action, and rendered the
Location parameter plus Language, Units, Source Preference, and Include Raw JSON
settings without errors.

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
da944eca936e279d77909db48ffe59fe737c851c1af91157d0e1606906bbf2e7
```

Dify Community Edition 1.19.0 was tested through the local package upload flow. Dify
Cloud was not exercised from this local environment. The package was fixed after the
first local install attempt exposed a plugin-daemon mirror dependency mismatch; the
final package pins a mirror-compatible `regex` version and contains only runtime
files.
