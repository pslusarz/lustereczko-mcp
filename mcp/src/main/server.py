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
from .tools.skills import register as _register_skills
from .tools.custom import register as _register_custom
from .tools.bidirectional_streaming import register as _register_streaming

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

_SILENT_TOOLS = {"write_server_log", "tail_server_log", "poll_ui_messages", "notify_agent"}

_register_skills(mcp)
_register_custom(mcp)
_register_streaming(mcp)


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


@mcp.tool(app=AppConfig(resource_uri="ui://display"))
def display_ui_to_user(
    html_fragment: Annotated[
        str,
        Field(
            description=(
                "HTML fragment; replaces #display-container. Inline <style>/<script> OK. "
                "External scripts/styles/images allowed from cdn.jsdelivr.net, unpkg.com, "
                "*.tile.openstreetmap.org. External <script src=...> in the fragment is "
                "unreliable (subsequent inline scripts may run before it loads); inject "
                "scripts dynamically (document.createElement('script')) and run init in "
                "onload. Do NOT use <iframe srcdoc> (sandbox blocks scripts). "
                "htmx + window.app available."
            )
        ),
    ],
) -> ToolResult:
    """Render an HTML fragment in the user's UI panel.

    Widget height — CRITICAL:
      window.innerHeight is hard-capped at 300px inside the lustereczko iframe.
      height:100%, flex:1, position:fixed, and all viewport-relative tricks collapse
      to 300px and do NOT work. The only correct approach: give the main content div
      an explicit pixel height (e.g. <div style="height:700px">). The panel
      auto-expands to fit content height, so explicit px values work correctly.
      Never use overflow:hidden on <body> — it clips content to 300px.

    UI->agent (MCP ext-apps; async, return Promises - params MUST be structured, not bare strings):
      window.app.updateModelContext({content: [{type: "text", text: "..."}]})
        attaches state for the next turn (no immediate model response).
      window.app.sendMessage({role: "user", content: [{type: "text", text: "..."}]})
        posts a chat reply (populates the user input box).
      window.app.callServerTool({name: "notify_agent", arguments: {event, channel_id, data}})
        enqueues a UI->agent message; agent drains it with poll_agent_messages(channel_id).

    Agent->UI: call notify_ui(event, channel_id, data); the UI polls with
      poll_ui_messages(channel_id).
    """
    return ToolResult(
        content=[TextContent(type="text", text="Content displayed to user.")],
        meta={"html": html_fragment},
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()
