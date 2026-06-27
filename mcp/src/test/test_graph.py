"""MCP tool-level tests for graph_query.

Isolation strategy: monkeypatch main.tools.graph._DB_PATH to a pytest tmp_path
so these tests never touch server-scratchpad/graph/ — safe to run alongside live apps.
"""

import json
import pytest
from fastmcp.client import Client
from main.server import mcp


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import main.tools.graph as _graph_mod
    monkeypatch.setattr(_graph_mod, "_DB_PATH", tmp_path / "test-graph")


@pytest.fixture
async def client():
    async with Client(transport=mcp) as c:
        yield c


# ── registration ─────────────────────────────────────────────────────────────

async def test_graph_query_registered(client):
    names = {t.name for t in await client.list_tools()}
    assert "graph_query" in names


# ── INSERT returns the created node(s) ───────────────────────────────────────

async def test_insert_returns_created_node(client):
    result = await client.call_tool("graph_query", {"query": "INSERT (:Thing {x: 1})"})
    rows = json.loads(result.content[0].text)
    assert len(rows) == 1
    node = next(iter(rows[0].values()))  # keyed by anonymous var e.g. "_anon_0"
    assert "Thing" in node["_labels"]
    assert node["x"] == 1


# ── round-trip: insert then match ────────────────────────────────────────────

async def test_match_after_insert(client):
    await client.call_tool("graph_query", {
        "query": "INSERT (:Person {name: 'Alix', age: 30})"
    })
    await client.call_tool("graph_query", {
        "query": "INSERT (:Person {name: 'Gus', age: 25})"
    })

    result = await client.call_tool("graph_query", {
        "query": "MATCH (p:Person) RETURN p.name, p.age ORDER BY p.age"
    })
    rows = json.loads(result.content[0].text)
    assert len(rows) == 2
    assert rows[0]["p.name"] == "Gus"
    assert rows[0]["p.age"] == 25
    assert rows[1]["p.name"] == "Alix"
    assert rows[1]["p.age"] == 30


async def test_relationship_match(client):
    await client.call_tool("graph_query", {
        "query": "INSERT (:Person {name: 'Alix'})"
    })
    await client.call_tool("graph_query", {
        "query": "INSERT (:Person {name: 'Gus'})"
    })
    await client.call_tool("graph_query", {
        "query": """
            MATCH (a:Person {name: 'Alix'}), (b:Person {name: 'Gus'})
            INSERT (a)-[:KNOWS {since: 2020}]->(b)
        """
    })

    result = await client.call_tool("graph_query", {
        "query": "MATCH (p:Person)-[:KNOWS]->(f) RETURN p.name, f.name"
    })
    rows = json.loads(result.content[0].text)
    assert len(rows) == 1
    assert rows[0]["p.name"] == "Alix"
    assert rows[0]["f.name"] == "Gus"


# ── empty match returns empty array ──────────────────────────────────────────

async def test_match_no_results(client):
    result = await client.call_tool("graph_query", {
        "query": "MATCH (n:DoesNotExist) RETURN n"
    })
    rows = json.loads(result.content[0].text)
    assert rows == []


# ── bad query surfaces as an error ───────────────────────────────────────────

async def test_invalid_query_raises(client):
    with pytest.raises(Exception):
        await client.call_tool("graph_query", {"query": "THIS IS NOT VALID GQL !!!"})
