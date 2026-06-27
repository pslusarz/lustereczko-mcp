import json
from pathlib import Path
from typing import Annotated

import grafeo
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent
from pydantic import Field

_DB_PATH = Path(__file__).parents[4] / "server-scratchpad" / "graph"


def _open_db() -> grafeo.GrafeoDB:
    _DB_PATH.mkdir(parents=True, exist_ok=True)
    return grafeo.GrafeoDB(str(_DB_PATH))


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def graph_query(
        query: Annotated[
            str,
            Field(description="Cypher query against the LPG style graph."),
        ],
    ) -> ToolResult:
        """Graph database backed by Grapheo. Returns a JSON array.

        Row keys are RETURN expressions for reads, variable names for writes:
          MATCH (p:Person) RETURN p.name  →  [{"p.name": "Alix"}, ...]
          INSERT (:Person {name: "Alix"}) →  [{"_anon_0": {"_id": 0, "_labels": ["Person"], "name": "Alix"}}, ...]
        """
        import main.tools.graph as _mod  # read _DB_PATH at call time so tests can monkeypatch it

        _mod._DB_PATH.mkdir(parents=True, exist_ok=True)
        db = grafeo.GrafeoDB(str(_mod._DB_PATH))
        try:
            result = db.execute(query)
            rows = [dict(row) for row in (result or [])]
            return ToolResult(
                content=[TextContent(type="text", text=json.dumps(rows, default=str, indent=2))]
            )
        finally:
            try:
                db.close()
            except AttributeError:
                pass
