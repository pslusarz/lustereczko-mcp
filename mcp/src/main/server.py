import logging
from pathlib import Path
from typing import Annotated

from pydantic import Field
from fastmcp import FastMCP
from fastmcp.apps.config import AppConfig, ResourceCSP
from fastmcp.server.middleware.logging import LoggingMiddleware
from fastmcp.server.middleware import MiddlewareContext
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent
from .templates import render_shell

_LOG_DIR = Path(__file__).parent.parent.parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.FileHandler(_LOG_DIR / "server.log"),
        logging.StreamHandler(),
    ],
)

mcp = FastMCP(
    "lustereczko",
    version="0.1.0",
    instructions=(
        "Render arbitrary HTML in the user's UI panel via display_ui_to_user. "
        "Use tail_server_log to inspect server logs when debugging. "
        "When running into issues or looking for examples, use list_agent_skills "
        "to discover available documentation and get_agent_skill to read it."
    ),
)
_SILENT_TOOLS = {"write_server_log", "tail_server_log"}

_SKILLS_DIR = Path(__file__).parents[3] / "skills" / "lustereczko-recipies" / "recipes"


class _ToolLoggingMiddleware(LoggingMiddleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        if context.message.name in _SILENT_TOOLS:
            return await call_next(context)
        return await super().on_call_tool(context, call_next)


mcp.add_middleware(_ToolLoggingMiddleware(logger=logging.getLogger(__name__), include_payloads=True))

_DISPLAY_CSP = ResourceCSP(
    resource_domains=[
        "https://cdn.jsdelivr.net",
        "https://unpkg.com",
        "https://*.tile.openstreetmap.org",
    ],
    connect_domains=["https://cdn.jsdelivr.net"],
)


@mcp.resource(
    "ui://display",
    mime_type="text/html;profile=mcp-app",
    app=AppConfig(csp=_DISPLAY_CSP),
)
def display_ui() -> str:
    return render_shell()


@mcp.tool()
def write_server_log(message: dict | str | None = None) -> ToolResult:
    """Write a message to the server log. The UI app can use this as a back channel to
    pass data (e.g. host capabilities, debug state) to the server; read it back with tail_server_log."""
    import json
    text = json.dumps(message, indent=2) if isinstance(message, dict) else str(message)
    logging.getLogger(__name__).info("UI log:\n%s", text)
    return ToolResult(content=[TextContent(type="text", text="Logged.")])


@mcp.tool()
def tail_server_log(n: Annotated[int, Field(description="Number of lines to return", default=50)] = 50) -> ToolResult:
    """Return the last n lines of the server log."""
    log_file = _LOG_DIR / "server.log"
    if not log_file.exists():
        return ToolResult(content=[TextContent(type="text", text="Log file not found.")])
    lines = log_file.read_text().splitlines()
    return ToolResult(content=[TextContent(type="text", text="\n".join(lines[-n:]))])


@mcp.tool()
def list_agent_skills() -> ToolResult:
    """List available agent skill slugs. Use get_agent_skill to read one."""
    if not _SKILLS_DIR.exists():
        return ToolResult(content=[TextContent(type="text", text="No skills available.")])
    slugs = [p.stem for p in sorted(_SKILLS_DIR.glob("*.md"))]
    return ToolResult(content=[TextContent(type="text", text="\n".join(slugs))])


@mcp.tool()
def get_agent_skill(
    slug: Annotated[str, Field(description="Skill slug from list_agent_skills, e.g. ui-debug")],
) -> ToolResult:
    """Read an agent skill document by slug."""
    path = _SKILLS_DIR / f"{slug}.md"
    if not path.exists():
        return ToolResult(content=[TextContent(type="text", text=f"Skill '{slug}' not found.")])
    return ToolResult(content=[TextContent(type="text", text=path.read_text())])


@mcp.tool(app=AppConfig(resource_uri="ui://display"))
def display_ui_to_user(
    html_fragment: Annotated[
        str,
        Field(
            description="HTML fragment; replaces #display-container. Inline <style>/<script> OK. External scripts/styles/images allowed from cdn.jsdelivr.net, unpkg.com, *.tile.openstreetmap.org. External <script src=...> in the fragment is unreliable (subsequent inline scripts may run before it loads); inject scripts dynamically (document.createElement('script')) and run init in onload. Do NOT use <iframe srcdoc> (sandbox blocks scripts). htmx + window.app available."
        ),
    ],
) -> ToolResult:
    """Render an HTML fragment in the user's UI panel.

    Available in-page (MCP ext-apps; both async, return Promises — params MUST be structured, not bare strings):
      window.app.updateModelContext({content: [{type: "text", text: "..."}]})
        attaches state for the next turn (no immediate model response). Preferred way to signal back to the LLM.
      window.app.sendMessage({role: "user", content: [{type: "text", text: "..."}]})
        posts a chat reply. Use as a fallback, since hosts implement it in a klunky manner.
    """
    return ToolResult(
        content=[TextContent(type="text", text="Content displayed to user.")],
        meta={"html": html_fragment},
    )


_custom_tools: dict[str, str] = {}


@mcp.tool()
def add_custom_tool(
    name: Annotated[str, Field(description="Unique name for this tool")],
    code: Annotated[str, Field(description="Python source string; must define a run(**kwargs) function")],
) -> ToolResult:
    """Save a Python code string as a named custom tool."""
    _custom_tools[name] = code
    return ToolResult(content=[TextContent(type="text", text=f"Custom tool '{name}' saved.")])


@mcp.tool()
def run_custom_tool(
    name: Annotated[str, Field(description="Name of a previously saved custom tool")],
    args: Annotated[dict, Field(description="Keyword arguments passed to the tool's run() function")] = {},
) -> ToolResult:
    """Execute a saved custom tool by name, passing args to its run() function."""
    if name not in _custom_tools:
        return ToolResult(content=[TextContent(type="text", text=f"No custom tool named '{name}'.")])
    namespace: dict = {}
    exec(_custom_tools[name], namespace)  # noqa: S102
    result = namespace["run"](**args)
    return ToolResult(content=[TextContent(type="text", text=str(result))])


def main():
    mcp.run()


if __name__ == "__main__":
    main()
