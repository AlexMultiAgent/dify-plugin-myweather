from __future__ import annotations

import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _manifest() -> dict:
    with (ROOT / "manifest.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_manifest_reserves_enough_memory_for_python_plugin():
    memory = _manifest()["resource"]["memory"]

    assert memory >= 256 * 1024 * 1024


def test_release_versions_are_synchronized():
    manifest = _manifest()
    with (ROOT / "pyproject.toml").open("rb") as handle:
        project_version = tomllib.load(handle)["project"]["version"]
    logic = (ROOT / "tools" / "weather_logic.py").read_text(encoding="utf-8")
    user_agent_version = re.search(
        r'USER_AGENT = "dify-myweather-plugin/([^"]+)"', logic
    )

    assert user_agent_version is not None
    assert manifest["version"] == manifest["meta"]["version"] == project_version
    assert user_agent_version.group(1) == project_version


def test_changelog_starts_with_the_current_release():
    with (ROOT / "pyproject.toml").open("rb") as handle:
        project_version = tomllib.load(handle)["project"]["version"]
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = re.findall(r"^## ([0-9]+\.[0-9]+\.[0-9]+)", changelog, re.MULTILINE)

    assert headings
    assert headings[0] == project_version


def test_runtime_requirements_are_fully_pinned():
    requirement_lines = [
        line.strip()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert requirement_lines
    assert all("==" in line for line in requirement_lines)


def test_manifest_declares_all_outbound_hosts():
    domains = set(_manifest()["network"]["domains"])

    assert domains == {
        "api.open-meteo.com",
        "geocoding-api.open-meteo.com",
        "wttr.in",
    }


def test_icon_assets_are_identical_safe_svg_files():
    root_icon = ROOT / "icon.svg"
    packaged_icon = ROOT / "_assets" / "icon.svg"

    assert root_icon.read_bytes() == packaged_icon.read_bytes()
    svg = ET.fromstring(root_icon.read_text(encoding="utf-8"))
    assert svg.attrib["viewBox"] == "0 0 256 256"
    assert not any(
        element.tag.rsplit("}", 1)[-1] in {"script", "foreignObject"}
        for element in svg.iter()
    )
