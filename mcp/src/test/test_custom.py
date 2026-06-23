import uuid


async def test_add_and_run_custom_tool(client):
    code = "def run(a, b): return a + b"
    save_result = await client.call_tool("add_custom_tool", {"name": "adder", "code": code})
    assert "saved" in save_result.content[0].text.lower()

    run_result = await client.call_tool("run_custom_tool", {"name": "adder", "args": {"a": 3, "b": 5}})
    assert run_result.content[0].text == "8"


async def test_add_overwrites_existing_tool(client):
    """Overwrite the same tool name twice with different sentinels.

    Each sentinel is a fresh UUID baked into the tool source, so a stale file
    or a caching bug will fail — the old code cannot return the new sentinel.
    """
    name = "sentinel_tool"

    for _ in range(2):
        sentinel = str(uuid.uuid4())
        await client.call_tool("add_custom_tool", {
            "name": name,
            "code": f"def run(**kwargs): return {sentinel!r}",
        })
        result = await client.call_tool("run_custom_tool", {"name": name, "args": {}})
        assert result.content[0].text == sentinel


async def test_run_custom_tool_unknown(client):
    result = await client.call_tool("run_custom_tool", {"name": "does-not-exist"}, raise_on_error=False)
    text = result.content[0].text.lower()
    assert "no custom tool" in text
    assert "available:" in text
