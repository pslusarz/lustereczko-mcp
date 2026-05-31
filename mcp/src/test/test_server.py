async def test_lifecycle_demo(client):
    pass


async def test_tools_registered(client):
    tools = await client.list_tools()
    names = {t.name for t in tools}
    assert {"display_ui_to_user", "write_server_log", "tail_server_log", "list_agent_skills", "get_agent_skill"} <= names


async def test_tail_server_log_returns_text(client):
    result = await client.call_tool("tail_server_log", {"n": 5})
    assert result.content
