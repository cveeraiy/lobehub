import json
import zipfile

import pytest

from app.routers.skills import _github_raw_url, _load_zip_skill_manifest, _manifest_from_text


def test_manifest_from_json_text():
    manifest = _manifest_from_text(
        json.dumps({"identifier": "demo", "name": "Demo", "description": "A demo"}),
        source={"type": "url"},
        fallback_name="skill.json",
    )

    assert manifest["identifier"] == "demo"
    assert manifest["name"] == "Demo"


def test_manifest_from_markdown_text():
    manifest = _manifest_from_text("# Prompt", source={"type": "url"}, fallback_name="agent.md")

    assert manifest["name"] == "agent"
    assert manifest["prompt"] == "# Prompt"


def test_github_raw_url_from_repo():
    assert (
        _github_raw_url("https://github.com/acme/skill-pack", "canary")
        == "https://raw.githubusercontent.com/acme/skill-pack/canary/SKILL.md"
    )


@pytest.mark.asyncio
async def test_load_zip_skill_manifest(tmp_path):
    archive_path = tmp_path / "skill.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("skill.json", json.dumps({"name": "Zip Skill", "description": "From zip"}))

    manifest = await _load_zip_skill_manifest(archive_path)

    assert manifest["name"] == "Zip Skill"
