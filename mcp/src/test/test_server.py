import json

# Rough token estimate: ~4 chars/token, consistent with major LLM tokenizers.
# Update _TOKEN_BUDGET when you intentionally expand the tool surface.
_TOKEN_BUDGET = 3262


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


async def test_lifecycle_demo(client):
    pass


async def test_tool_listing_token_footprint(client):
    tools = await client.list_tools()
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
