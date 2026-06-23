import re
from pathlib import Path
from typing import Annotated

from pydantic import Field
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent

_TOOLS_DIR = Path(__file__).parents[4] / "server-scratchpad" / "tools"

_TOOL_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _tool_path(name: str) -> Path:
    if not _TOOL_NAME_RE.match(name):
        raise ValueError(
            f"Invalid tool name {name!r}: must be 1-64 alphanumeric/hyphen/underscore characters."
        )
    return _TOOLS_DIR / f"{name}.py"


def _add_tool(name: str, code: str) -> None:
    _TOOLS_DIR.mkdir(exist_ok=True)
    path = _tool_path(name)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(code)
    tmp.rename(path)


def _load_tool(name: str) -> str | None:
    path = _tool_path(name)
    return path.read_text() if path.exists() else None


def _list_tool_names() -> list[str]:
    if not _TOOLS_DIR.exists():
        return []
    return sorted(p.stem for p in _TOOLS_DIR.glob("*.py"))


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
        code = _load_tool(name)
        if code is None:
            available = ", ".join(_list_tool_names()) or "none"
            return ToolResult(content=[TextContent(type="text", text=f"No custom tool named '{name}'. Available: {available}.")])
        namespace: dict = {}
        exec(code, namespace)  # noqa: S102
        result = namespace["run"](**args)
        return ToolResult(content=[TextContent(type="text", text=str(result))])
