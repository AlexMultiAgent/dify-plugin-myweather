# Dify Marketplace Release Flow

This project follows the Marketplace process documented by
[`langgenius/dify-plugins`](https://github.com/langgenius/dify-plugins):

1. Increment the version in `manifest.yaml`, `pyproject.toml`, `USER_AGENT`, and
   `CHANGELOG.md`.
2. Run the full test, lint, type, dependency-audit, package-build, and package-
   verification gates.
3. Create and push the matching `vX.Y.Z` Git tag. CI publishes a GitHub Release
   with the versioned `.difypkg` attached.
4. Fork `langgenius/dify-plugins` and update
   `AlexMultiAgent/myweather/myweather-X.Y.Z.difypkg`.
5. Open a Marketplace PR against `main` using the official PR template.

For version updates, the Marketplace requires the PR to contain exactly one new
file: the current `.difypkg`. Source changes remain in this repository, and older
versions are distributed through GitHub Releases. Do not include local paths,
credentials, caches, or unrelated cleanup in the Marketplace PR.

The update PR body should be prepared from
[`PR_BODY_v0.1.4.md`](./PR_BODY_v0.1.4.md). The package must first pass:

```bash
uv run python scripts/verify_package.py myweather-X.Y.Z.difypkg --source-root .
```

Official references:

- [Marketplace publishing process](https://github.com/langgenius/dify-plugins#publishing-to-dify-marketplace)
- [Marketplace curation policy](https://github.com/langgenius/dify-plugins/blob/main/docs/marketplace-curation-policy.md)
- [Plugin submission requirements](https://github.com/langgenius/dify-plugins/blob/main/docs/plugin-submission-requirements.md)
- [Marketplace PR template](https://github.com/langgenius/dify-plugins/blob/main/.github/pull_request_template.md)
