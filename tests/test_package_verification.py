from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_package.py"
REQUIRED = (
    "LICENSE",
    "PRIVACY.md",
    "README.md",
    "_assets/icon.svg",
    "icon.svg",
    "manifest.yaml",
    "main.py",
    "pyproject.toml",
    "requirements.txt",
    "provider/__init__.py",
    "provider/myweather.py",
    "provider/myweather.yaml",
    "tools/__init__.py",
    "tools/weather_lookup.py",
    "tools/weather_lookup.yaml",
    "tools/weather_logic.py",
    "tools/translations.py",
    "tools/transliteration.py",
    "readme/README_zh_Hans.md",
)


def _write_package(path: Path, *, extra: str | None = None) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name in REQUIRED:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            archive.writestr(info, (ROOT / name).read_bytes())
        if extra is not None:
            archive.writestr(extra, "not part of the runtime package")


def _run_verifier(package: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            str(package),
            "--source-root",
            str(ROOT),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_package_verifier_accepts_a_complete_runtime_archive(tmp_path):
    package = tmp_path / "myweather.difypkg"
    _write_package(package)

    result = _run_verifier(package)

    assert result.returncode == 0, result.stderr
    assert "verified" in result.stdout


@pytest.mark.parametrize(
    "extra", ["tests/test_secret.py", "CHANGELOG.md", "output/test-artifact.txt"]
)
def test_package_verifier_rejects_development_files(tmp_path, extra):
    package = tmp_path / "myweather.difypkg"
    _write_package(package, extra=extra)

    result = _run_verifier(package)

    assert result.returncode != 0
    assert "forbidden" in result.stderr.lower()
