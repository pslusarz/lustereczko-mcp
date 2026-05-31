# Claude Desktop (and some other MCP hosts) spawns multiple server processes — one for the UI
# and one for the LLM agent — that do not share memory. A tool added by the agent process is
# invisible to the UI process and vice versa. To bridge this, tools are persisted to a JSON
# file on disk so every process reads the same state. File locking prevents concurrent writes
# from corrupting it. There is no in-memory cache: every call reads from disk so all processes
# always see the current state without any invalidation logic.

import fcntl
import json
from pathlib import Path
from typing import Annotated

from pydantic import Field
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent

_SCRATCHPAD_DIR = Path(__file__).parents[4] / "server-scratchpad"
_SCRATCHPAD_DIR.mkdir(exist_ok=True)
_TOOLS_FILE = _SCRATCHPAD_DIR / "tools.json"


def _load_tools() -> dict[str, str]:
    if not _TOOLS_FILE.exists():
        return {}
    with _TOOLS_FILE.open() as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            return json.load(f)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _add_tool(name: str, code: str) -> None:
    # Hold an exclusive lock across the full read-modify-write so concurrent processes
    # cannot clobber each other's tools.
    _TOOLS_FILE.touch(exist_ok=True)
    with _TOOLS_FILE.open("r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            content = f.read()
            tools = json.loads(content) if content.strip() else {}
            tools[name] = code
            f.seek(0)
            f.truncate()
            json.dump(tools, f)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def add_custom_tool(  # pyright: ignore[reportUnusedFunction]
        name: Annotated[str, Field(description="Unique name for this tool")],
        code: Annotated[str, Field(description="Python source string; must define a run(**kwargs) function")],
    ) -> ToolResult:
        """Save a Python code string as a named custom tool. The code runs on the server and can access the local filesystem using absolute paths. See best-practices:ui-agent-communication for patterns."""
        _add_tool(name, code)
        return ToolResult(content=[TextContent(type="text", text=f"Custom tool '{name}' saved.")])

    @mcp.tool()
    def run_custom_tool(  # pyright: ignore[reportUnusedFunction]
        name: Annotated[str, Field(description="Name of a previously saved custom tool")],
        args: Annotated[dict, Field(description="Keyword arguments passed to the tool's run() function")] = {},
    ) -> ToolResult:
        """Execute a saved custom tool by name, passing args to its run() function."""
        tools = _load_tools()
        if name not in tools:
            available = ", ".join(tools) or "none"
            return ToolResult(content=[TextContent(type="text", text=f"No custom tool named '{name}'. Available: {available}.")])
        namespace: dict = {}
        exec(tools[name], namespace)  # noqa: S102
        result = namespace["run"](**args)
        return ToolResult(content=[TextContent(type="text", text=str(result))])
