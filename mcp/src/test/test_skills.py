import pytest
from main.tools.skills import _SKILLS_DIR, AgentSkillList, _skill_name, _skill_path


async def test_list_agent_skills(client):
    result = await client.call_tool("list_agent_skills", {})
    skill_list = AgentSkillList.model_validate_json(result.content[0].text)
    names = {s.skill_name for s in skill_list.skills}
    assert "recipes:ui-debug" in names
    assert "recipes:host-capabilities" in names
    for skill in skill_list.skills:
        assert skill.description, f"{skill.skill_name} has no description"


async def test_get_agent_skill(client):
    result = await client.call_tool("get_agent_skill", {"skill_name": "recipes:ui-debug"})
    assert result.content
    assert "debug" in result.content[0].text.lower()


async def test_get_agent_skill_unknown(client):
    result = await client.call_tool("get_agent_skill", {"skill_name": "does-not-exist"}, raise_on_error=False)
    assert "not found" in result.content[0].text.lower()


def test_skills_dir_has_files():
    assert list(_SKILLS_DIR.rglob("*.md")), f"No .md files found in {_SKILLS_DIR}"


@pytest.mark.parametrize(
    "path",
    [p for p in _SKILLS_DIR.rglob("*.md") if p.stem != "SKILL"],
    ids=lambda p: _skill_name(p),
)
async def test_skill_content_matches_file(client, path):
    result = await client.call_tool("get_agent_skill", {"skill_name": _skill_name(path)})
    assert result.content[0].text == path.read_text()
