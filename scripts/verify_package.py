#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path, PurePosixPath

REQUIRED_FILES = (
    "LICENSE",
    "PRIVACY.md",
    "README.md",
    "_assets/icon.svg",
    "icon.svg",
    "main.py",
    "manifest.yaml",
    "provider/__init__.py",
    "provider/myweather.py",
    "provider/myweather.yaml",
    "pyproject.toml",
    "readme/README_zh_Hans.md",
    "requirements.txt",
    "tools/__init__.py",
    "tools/translations.py",
    "tools/transliteration.py",
    "tools/weather_logic.py",
    "tools/weather_lookup.py",
    "tools/weather_lookup.yaml",
)

FORBIDDEN_DIRECTORIES = frozenset(
    {
        ".claude",
        ".codex",
        ".git",
        ".github",
        ".playwright-mcp",
        ".pytest_cache",
        ".remember",
        ".ruff_cache",
        ".superpowers",
        ".venv",
        "__pycache__",
        "docs",
        "output",
        "scripts",
        "tests",
        "venv",
    }
)

FORBIDDEN_FILES = frozenset(
    {
        ".claude.local.md",
        ".difyignore",
        ".env",
        ".env.example",
        ".gitignore",
        "CHANGELOG.md",
        "MARKETPLACE_CHECKLIST.md",
        "uv.lock",
    }
)


class PackageVerificationError(RuntimeError):
    """Raised when a Dify plugin archive violates the release contract."""


def _forbidden_reason(name: str) -> str | None:
    path = PurePosixPath(name)
    if any(part in FORBIDDEN_DIRECTORIES for part in path.parts):
        return "development or local directory"
    if path.name in FORBIDDEN_FILES:
        return "development-only file"
    if path.name.startswith(".env"):
        return "environment file"
    if path.suffix in {".difypkg", ".pyc"}:
        return "generated artifact"
    return None


def verify_package(package_path: Path, source_root: Path) -> int:
    if not package_path.is_file():
        raise PackageVerificationError(f"package does not exist: {package_path}")
    if not source_root.is_dir():
        raise PackageVerificationError(f"source root does not exist: {source_root}")

    try:
        with zipfile.ZipFile(package_path) as archive:
            names = archive.namelist()
            duplicate_names = sorted({name for name in names if names.count(name) > 1})
            if duplicate_names:
                raise PackageVerificationError(
                    f"duplicate archive entries: {', '.join(duplicate_names)}"
                )

            missing = sorted(set(REQUIRED_FILES) - set(names))
            if missing:
                raise PackageVerificationError(
                    f"missing runtime files: {', '.join(missing)}"
                )

            forbidden = {
                name: reason
                for name in names
                if (reason := _forbidden_reason(name)) is not None
            }
            if forbidden:
                details = ", ".join(
                    f"{name} ({reason})" for name, reason in sorted(forbidden.items())
                )
                raise PackageVerificationError(f"forbidden entries: {details}")

            corrupt = archive.testzip()
            if corrupt is not None:
                raise PackageVerificationError(f"corrupt archive entry: {corrupt}")

            mismatched = [
                name
                for name in REQUIRED_FILES
                if archive.read(name) != (source_root / name).read_bytes()
            ]
            if mismatched:
                raise PackageVerificationError(
                    f"packaged files differ from source: {', '.join(mismatched)}"
                )
    except zipfile.BadZipFile as exc:
        raise PackageVerificationError(f"invalid ZIP archive: {exc}") from exc

    return len(names)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the runtime contents of a Dify plugin package."
    )
    parser.add_argument("package", type=Path)
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path.cwd(),
        help="Plugin source directory used for byte-for-byte comparisons.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        entry_count = verify_package(args.package, args.source_root)
    except (OSError, PackageVerificationError) as exc:
        print(f"Package verification failed: {exc}", file=sys.stderr)
        return 1
    print(f"verified {entry_count} runtime entries in {args.package}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
