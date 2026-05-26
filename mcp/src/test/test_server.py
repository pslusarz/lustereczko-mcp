import pytest
from fastmcp.client import Client
from main.server import mcp, _SKILLS_DIR


@pytest.fixture
async def client():
    async with Client(transport=mcp) as c:
        yield c


async def test_tools_registered(client):
    tools = await client.list_tools()
    names = {t.name for t in tools}
    assert {"display_ui_to_user", "write_server_log", "tail_server_log", "list_agent_skills", "get_agent_skill"} <= names


async def test_list_agent_skills(client):
    result = await client.call_tool("list_agent_skills", {})
    slugs = result.content[0].text.splitlines()
    assert "ui-debug" in slugs
    assert "host-capabilities" in slugs


async def test_get_agent_skill(client):
    result = await client.call_tool("get_agent_skill", {"slug": "ui-debug"})
    assert result.content
    assert "debug" in result.content[0].text.lower()


async def test_get_agent_skill_unknown(client):
    result = await client.call_tool("get_agent_skill", {"slug": "does-not-exist"}, raise_on_error=False)
    assert "not found" in result.content[0].text.lower()


def test_skills_dir_has_files():
    assert list(_SKILLS_DIR.glob("*.md")), f"No .md files found in {_SKILLS_DIR}"


@pytest.mark.parametrize("path", list(_SKILLS_DIR.glob("*.md")), ids=lambda p: p.stem)
async def test_skill_content_matches_file(client, path):
    result = await client.call_tool("get_agent_skill", {"slug": path.stem})
    assert result.content[0].text == path.read_text()


async def test_tail_server_log_returns_text(client):
    result = await client.call_tool("tail_server_log", {"n": 5})
    assert result.content


async def test_add_and_run_custom_tool(client):
    code = "def run(a, b): return a + b"
    save_result = await client.call_tool("add_custom_tool", {"name": "adder", "code": code})
    assert "saved" in save_result.content[0].text.lower()

    run_result = await client.call_tool("run_custom_tool", {"name": "adder", "args": {"a": 3, "b": 5}})
    assert run_result.content[0].text == "8"


async def test_run_custom_tool_unknown(client):
    result = await client.call_tool("run_custom_tool", {"name": "does-not-exist"}, raise_on_error=False)
    text = result.content[0].text.lower()
    assert "no custom tool" in text
    assert "available:" in text
