import asyncio
import json


async def test_streaming_tools_registered(client):
    tools = await client.list_tools()
    names = {t.name for t in tools}
    assert {"notify_ui", "poll_ui_messages", "notify_agent", "poll_agent_messages"} <= names


async def test_poll_ui_messages_empty(client):
    await client.call_tool("poll_ui_messages", {})
    result = await client.call_tool("poll_ui_messages", {})
    assert json.loads(result.content[0].text) == []


async def test_poll_agent_messages_empty(client):
    await client.call_tool("poll_agent_messages", {})
    result = await client.call_tool("poll_agent_messages", {})
    assert json.loads(result.content[0].text) == []


async def test_notify_ui_and_poll(client):
    await client.call_tool("poll_ui_messages", {})
    await client.call_tool("notify_ui", {"event": "test:ui", "data": {"x": 1}})
    result = await client.call_tool("poll_ui_messages", {})
    items = json.loads(result.content[0].text)
    assert any(item["event"] == "test:ui" for item in items)


async def test_notify_agent_and_poll(client):
    await client.call_tool("poll_agent_messages", {})
    await client.call_tool("notify_agent", {"event": "ui:action", "data": {"btn": "ok"}})
    result = await client.call_tool("poll_agent_messages", {})
    items = json.loads(result.content[0].text)
    assert any(item["event"] == "ui:action" for item in items)


async def test_drain_clears_queue(client):
    await client.call_tool("poll_ui_messages", {})
    await client.call_tool("notify_ui", {"event": "once", "data": None})
    await client.call_tool("poll_ui_messages", {})
    result = await client.call_tool("poll_ui_messages", {})
    assert json.loads(result.content[0].text) == []


async def test_fifo_order(client):
    await client.call_tool("poll_ui_messages", {})
    for i in range(5):
        await client.call_tool("notify_ui", {"event": "seq", "data": {"i": i}})
    result = await client.call_tool("poll_ui_messages", {})
    items = json.loads(result.content[0].text)
    assert [item["data"]["i"] for item in items] == list(range(5))


async def test_queues_are_independent(client):
    await client.call_tool("poll_ui_messages", {})
    await client.call_tool("poll_agent_messages", {})
    await client.call_tool("notify_ui", {"event": "for:ui"})
    result = await client.call_tool("poll_agent_messages", {})
    assert json.loads(result.content[0].text) == []


async def test_concurrent_writes_no_data_loss(client):
    await client.call_tool("poll_ui_messages", {})
    n = 20
    await asyncio.gather(
        *[client.call_tool("notify_ui", {"event": "burst", "data": {"i": i}}) for i in range(n)]
    )
    result = await client.call_tool("poll_ui_messages", {})
    items = json.loads(result.content[0].text)
    assert len(items) == n
