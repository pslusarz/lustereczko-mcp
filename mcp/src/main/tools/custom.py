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


def _save_tools(tools: dict[str, str]) -> None:
    with _TOOLS_FILE.open("w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(tools, f)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


_custom_tools: dict[str, str] = _load_tools()


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def add_custom_tool(
        name: Annotated[str, Field(description="Unique name for this tool")],
        code: Annotated[str, Field(description="Python source string; must define a run(**kwargs) function")],
    ) -> ToolResult:
        """Save a Python code string as a named custom tool."""
        _custom_tools[name] = code
        _save_tools(_custom_tools)
        return ToolResult(content=[TextContent(type="text", text=f"Custom tool '{name}' saved.")])

    @mcp.tool()
    def run_custom_tool(
        name: Annotated[str, Field(description="Name of a previously saved custom tool")],
        args: Annotated[dict, Field(description="Keyword arguments passed to the tool's run() function")] = {},
    ) -> ToolResult:
        """Execute a saved custom tool by name, passing args to its run() function."""
        if name not in _custom_tools:
            _custom_tools.update(_load_tools())
        if name not in _custom_tools:
            available = ", ".join(_custom_tools) or "none"
            return ToolResult(content=[TextContent(type="text", text=f"No custom tool named '{name}'. Available: {available}.")])
        namespace: dict = {}
        exec(_custom_tools[name], namespace)  # noqa: S102
        result = namespace["run"](**args)
        return ToolResult(content=[TextContent(type="text", text=str(result))])
