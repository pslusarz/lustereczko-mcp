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
