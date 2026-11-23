# Security Policy

## Reporting a vulnerability

Report suspected vulnerabilities privately through GitHub's private
vulnerability reporting form:

- https://github.com/AlexMultiAgent/dify-plugin-myweather/security/advisories/new

The form opens a private advisory that only the maintainers can read. Do not
open a public issue for a vulnerability report.

If the advisory form is unavailable, the maintainer contact declared in
`manifest.yaml` is `AlexMultiAgent@users.noreply.github.com`. That is a GitHub
noreply address, so prefer the advisory form above.

## What counts as a vulnerability

MyWeather is a Python plugin that runs inside the Dify plugin daemon. In scope:

- A crafted `location` query that makes the plugin read files outside its own
  directory, escape the plugin sandbox, or run unexpected code.
- Path traversal or unsafe file handling in the lookup or packaging logic.
- An upstream provider request that is manipulated into returning data the tool
  did not document, or into leaking user input to a third party.
- A vulnerable runtime dependency that is reachable from the shipped code.

Out of scope:

- Wrong or missing weather data, or a place name that resolves to the wrong
  location.
- Unavailability of wttr.in or Open-Meteo.
- Issues in Dify, in the plugin daemon, or in the upstream providers.

## What to expect

- We aim to acknowledge a report within 7 days and to publish a fix or an
  advisory within 90 days of the acknowledgement.
- We keep the advisory private while the fix is prepared and released.
- We credit the reporter in the advisory unless anonymity is requested.

## Disclosure

- Public disclosure happens through a GitHub Security Advisory on this
  repository, together with the release that carries the fix.
- The disclosure timeline is 90 days from acknowledgement. If a fix needs
  longer, we publish an advisory that explains the delay.
- We ask reporters to keep the details of any vulnerabilities private until
  the disclosure date.

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.5 | Yes — current release |
| 0.1.4 | No — superseded by 0.1.5 |

Only the latest published release receives fixes; older versions are not
maintained.
