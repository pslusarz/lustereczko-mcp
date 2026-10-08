import json

# Rough token estimate: ~4 chars/token, consistent with major LLM tokenizers.
# Update _TOKEN_BUDGET when you intentionally expand the tool surface.
_TOKEN_BUDGET = 2630

_APP_ONLY_TOOLS = {"notify_agent", "write_server_log", "poll_ui_messages"}


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _visibility(tool) -> list[str] | None:
    return ((tool.meta or {}).get("ui") or {}).get("visibility")


def _model_visible(tools):
    return [t for t in tools if _visibility(t) in (None, []) or "model" in _visibility(t)]


async def test_lifecycle_demo(client):
    pass


async def test_tool_listing_token_footprint(client):
    tools = _model_visible(await client.list_tools())
    payload = json.dumps(
        [t.model_dump(exclude_none=True) for t in tools],
        indent=2,
    )
    token_count = _approx_tokens(payload)
    print(f"\n--- tool listing as seen by agent ---\n{payload}\n\napprox tokens: {token_count} / {_TOKEN_BUDGET}")
    assert token_count <= _TOKEN_BUDGET, (
        f"Tool listing is {token_count} tokens, budget is {_TOKEN_BUDGET}. "
        "If the growth is intentional, update _TOKEN_BUDGET here and the agent should also updatethe footprint number in README.md for the project."
    )


async def test_tools_registered(client):
    tools = await client.list_tools()
    names = {t.name for t in tools}
    assert {"display_ui_to_user", "write_server_log", "tail_server_log", "list_agent_skills", "get_agent_skill"} <= names


async def test_tail_server_log_returns_text(client):
    result = await client.call_tool("tail_server_log", {"n": 5})
    assert result.content


async def test_ui_only_tools_are_app_visible_only(client):
    tools = {t.name: t for t in await client.list_tools()}
    for name in _APP_ONLY_TOOLS:
        assert _visibility(tools[name]) == ["app"], name
    assert {t.name for t in _model_visible(tools.values())}.isdisjoint(_APP_ONLY_TOOLS)


async def test_app_only_tools_remain_callable(client):
    result = await client.call_tool("write_server_log", {"message": "visibility check"})
    assert result.content[0].text == "Logged."


async def test_display_shell_pins_ext_apps_major_version(client):
    result = await client.read_resource("ui://display")
    html = result[0].text
    assert "@modelcontextprotocol/ext-apps@2/" in html
    assert "ext-apps@latest" not in html
