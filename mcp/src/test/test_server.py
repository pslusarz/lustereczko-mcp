import pytest
from fastmcp.client import Client
from main.server import mcp


@pytest.fixture
async def client():
    async with Client(transport=mcp) as c:
        yield c


async def test_tools_registered(client):
    tools = await client.list_tools()
    names = {t.name for t in tools}
    assert {"display_ui_to_user", "tail_log", "read_resource", "log_init_result"} <= names


async def test_recipes_registered(client):
    resources = await client.list_resources()
    uris = {str(r.uri) for r in resources}
    assert "skill://recipes/ui-debug" in uris
    assert "skill://recipes/host-capabilities" in uris


async def test_read_recipe(client):
    result = await client.read_resource("skill://recipes/host-capabilities")
    assert result
    assert "getHostCapabilities" in result[0].text


async def test_read_resource_tool(client):
    result = await client.call_tool("read_resource", {"uri": "skill://recipes/ui-debug"})
    assert result.content
    assert len(result.content[0].text) > 0


async def test_tail_log_returns_text(client):
    result = await client.call_tool("tail_log", {"n": 5})
    assert result.content
