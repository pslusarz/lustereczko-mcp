"""Tests for bidirectional_streaming tools with per-channel isolation.

Each test uses a unique channel_id so tests are fully independent of each
other and of any live server state.
"""

import asyncio
import json

import pytest


# ── helpers ───────────────────────────────────────────────────────────────────


async def drain_ui(client, ch: str) -> None:
    await client.call_tool("poll_ui_messages", {"channel_id": ch})


async def drain_agent(client, ch: str) -> None:
    await client.call_tool("poll_agent_messages", {"channel_id": ch})


async def ui_items(client, ch: str) -> list:
    r = await client.call_tool("poll_ui_messages", {"channel_id": ch})
    return json.loads(r.content[0].text)


async def agent_items(client, ch: str) -> list:
    r = await client.call_tool("poll_agent_messages", {"channel_id": ch})
    return json.loads(r.content[0].text)


# ── tool registration ─────────────────────────────────────────────────────────


async def test_streaming_tools_registered(client):
    tools = await client.list_tools()
    names = {t.name for t in tools}
    assert {"notify_ui", "poll_ui_messages", "notify_agent", "poll_agent_messages"} <= names


# ── basic round-trips ─────────────────────────────────────────────────────────


async def test_notify_ui_and_poll(client):
    ch = "basic-ui"
    await drain_ui(client, ch)
    await client.call_tool("notify_ui", {"channel_id": ch, "event": "test:ui", "data": {"x": 1}})
    items = await ui_items(client, ch)
    assert any(i["event"] == "test:ui" for i in items)


async def test_notify_agent_and_poll(client):
    ch = "basic-agent"
    await drain_agent(client, ch)
    await client.call_tool("notify_agent", {"channel_id": ch, "event": "ui:action", "data": {"btn": "ok"}})
    items = await agent_items(client, ch)
    assert any(i["event"] == "ui:action" for i in items)


# ── empty / drain semantics ───────────────────────────────────────────────────


async def test_poll_ui_messages_empty(client):
    ch = "empty-ui"
    await drain_ui(client, ch)
    assert await ui_items(client, ch) == []


async def test_poll_agent_messages_empty(client):
    ch = "empty-agent"
    await drain_agent(client, ch)
    assert await agent_items(client, ch) == []


async def test_drain_clears_queue(client):
    ch = "drain-clears"
    await drain_ui(client, ch)
    await client.call_tool("notify_ui", {"channel_id": ch, "event": "once", "data": None})
    await drain_ui(client, ch)
    assert await ui_items(client, ch) == []


# ── FIFO order ────────────────────────────────────────────────────────────────


async def test_fifo_order(client):
    ch = "fifo-order"
    await drain_ui(client, ch)
    for i in range(5):
        await client.call_tool("notify_ui", {"channel_id": ch, "event": "seq", "data": {"i": i}})
    items = await ui_items(client, ch)
    assert [item["data"]["i"] for item in items] == list(range(5))


# ── ui vs agent queues are independent within the same channel ────────────────


async def test_ui_and_agent_queues_independent(client):
    ch = "same-ch-independence"
    await drain_ui(client, ch)
    await drain_agent(client, ch)
    await client.call_tool("notify_ui", {"channel_id": ch, "event": "for-ui"})
    # must NOT bleed into the agent queue
    assert await agent_items(client, ch) == []
    # must appear in the ui queue
    items = await ui_items(client, ch)
    assert any(i["event"] == "for-ui" for i in items)


# ── CHANNEL ISOLATION ─────────────────────────────────────────────────────────


async def test_channels_do_not_share_ui_queue(client):
    """Messages written to channel A must be invisible to channel B."""
    ch_a, ch_b = "iso-ui-a", "iso-ui-b"
    await drain_ui(client, ch_a)
    await drain_ui(client, ch_b)

    await client.call_tool("notify_ui", {"channel_id": ch_a, "event": "ping", "data": {"src": "a"}})

    assert await ui_items(client, ch_b) == [], \
        "channel B must not receive messages sent to channel A"
    items_a = await ui_items(client, ch_a)
    assert len(items_a) == 1 and items_a[0]["data"]["src"] == "a"


async def test_channels_do_not_share_agent_queue(client):
    """Acks written by channel A must be invisible to channel B's agent poll."""
    ch_a, ch_b = "iso-agent-a", "iso-agent-b"
    await drain_agent(client, ch_a)
    await drain_agent(client, ch_b)

    await client.call_tool("notify_agent", {"channel_id": ch_a, "event": "ack", "data": {"id": 1}})

    assert await agent_items(client, ch_b) == [], \
        "channel B must not receive acks sent by channel A"
    items_a = await agent_items(client, ch_a)
    assert len(items_a) == 1 and items_a[0]["data"]["id"] == 1


async def test_drain_channel_a_does_not_affect_channel_b(client):
    """Draining channel A leaves channel B's queue intact."""
    ch_a, ch_b = "drain-iso-a", "drain-iso-b"
    await drain_ui(client, ch_a)
    await drain_ui(client, ch_b)

    await client.call_tool("notify_ui", {"channel_id": ch_a, "event": "msg-a", "data": None})
    await client.call_tool("notify_ui", {"channel_id": ch_b, "event": "msg-b", "data": None})

    await drain_ui(client, ch_a)  # drain A only

    items_b = await ui_items(client, ch_b)
    assert any(i["event"] == "msg-b" for i in items_b), \
        "channel B's message must survive draining channel A"
    assert not any(i["event"] == "msg-a" for i in items_b), \
        "channel A's message must not appear in channel B"


async def test_multiple_channels_independent_fifo(client):
    """Each channel maintains its own FIFO; orders don't bleed across channels."""
    channels = ["multi-x", "multi-y", "multi-z"]
    for ch in channels:
        await drain_ui(client, ch)

    for ch in channels:
        for i in range(4):
            await client.call_tool("notify_ui", {"channel_id": ch, "event": "seq", "data": {"ch": ch, "i": i}})

    for ch in channels:
        items = await ui_items(client, ch)
        assert len(items) == 4, f"{ch}: expected 4 items, got {len(items)}"
        assert [item["data"]["i"] for item in items] == [0, 1, 2, 3], \
            f"{ch}: FIFO order broken"
        assert all(item["data"]["ch"] == ch for item in items), \
            f"{ch}: received message belonging to a different channel"


async def test_concurrent_writes_same_channel_no_data_loss(client):
    """Concurrent writes to the same channel must not lose items (flock test)."""
    ch = "concurrent-same"
    await drain_ui(client, ch)
    n = 20
    await asyncio.gather(
        *[client.call_tool("notify_ui", {"channel_id": ch, "event": "burst", "data": {"i": i}}) for i in range(n)]
    )
    items = await ui_items(client, ch)
    assert len(items) == n, f"expected {n} items, got {len(items)}"


async def test_concurrent_writes_across_channels_no_data_loss(client):
    """Concurrent writes to different channels must not lose or cross-contaminate items."""
    ch_a, ch_b = "concurrent-a", "concurrent-b"
    await drain_ui(client, ch_a)
    await drain_ui(client, ch_b)

    n = 15
    await asyncio.gather(
        *[client.call_tool("notify_ui", {"channel_id": ch_a, "event": "burst", "data": {"i": i, "ch": "a"}}) for i in range(n)],
        *[client.call_tool("notify_ui", {"channel_id": ch_b, "event": "burst", "data": {"i": i, "ch": "b"}}) for i in range(n)],
    )

    items_a = await ui_items(client, ch_a)
    items_b = await ui_items(client, ch_b)

    assert len(items_a) == n, f"channel A: expected {n}, got {len(items_a)}"
    assert len(items_b) == n, f"channel B: expected {n}, got {len(items_b)}"
    assert all(i["data"]["ch"] == "a" for i in items_a), "channel A contains B's messages"
    assert all(i["data"]["ch"] == "b" for i in items_b), "channel B contains A's messages"


async def test_full_roundtrip_per_channel(client):
    """Simulate the real protocol: UI announces ready, agent pings, UI acks."""
    ch = "roundtrip"
    await drain_ui(client, ch)
    await drain_agent(client, ch)

    # UI → agent: ready handshake
    await client.call_tool("notify_agent", {"channel_id": ch, "event": "ready", "data": {"channel_id": ch}})
    handshake = await agent_items(client, ch)
    assert handshake[0]["event"] == "ready"
    assert handshake[0]["data"]["channel_id"] == ch

    # agent → UI: send 5 pings
    for i in range(1, 6):
        await client.call_tool("notify_ui", {"channel_id": ch, "event": "ping", "data": {"id": i}})

    pings = await ui_items(client, ch)
    assert [p["data"]["id"] for p in pings] == [1, 2, 3, 4, 5]

    # UI → agent: ack each ping
    for ping in pings:
        await client.call_tool("notify_agent", {"channel_id": ch, "event": "ack", "data": {"id": ping["data"]["id"]}})

    acks = await agent_items(client, ch)
    assert len(acks) == 5
    assert {a["data"]["id"] for a in acks} == {1, 2, 3, 4, 5}


# ── security: invalid channel_id ──────────────────────────────────────────────


async def test_path_traversal_rejected(client):
    """channel_id containing path separators must be rejected."""
    with pytest.raises(Exception):
        await client.call_tool("notify_ui", {"channel_id": "../evil", "event": "x"})


async def test_empty_channel_id_rejected(client):
    with pytest.raises(Exception):
        await client.call_tool("notify_ui", {"channel_id": "", "event": "x"})


async def test_too_long_channel_id_rejected(client):
    with pytest.raises(Exception):
        await client.call_tool("notify_ui", {"channel_id": "a" * 65, "event": "x"})


async def test_special_chars_in_channel_id_rejected(client):
    for bad in ["ch@1", "ch/2", "ch 3", "ch.4", "ch!5"]:
        with pytest.raises(Exception):
            await client.call_tool("notify_ui", {"channel_id": bad, "event": "x"})
