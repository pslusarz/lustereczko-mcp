import fcntl
import json
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
_SILENT_TOOLS = {"write_server_log", "tail_server_log", "poll_agent_notifications"}

_QUEUE_FILE = _LOG_DIR / "notifications.json"


def _queue_append(event: str, data) -> None:
    _QUEUE_FILE.touch(exist_ok=True)
    with open(_QUEUE_FILE, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        content = f.read().strip()
        items = json.loads(content) if content else []
        items.append({"event": event, "data": data})
        f.seek(0)
        f.truncate()
        json.dump(items, f)


def _queue_drain() -> list:
    _QUEUE_FILE.touch(exist_ok=True)
    with open(_QUEUE_FILE, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        content = f.read().strip()
        items = json.loads(content) if content else []
        f.seek(0)
        f.truncate()
        json.dump([], f)
    return items
_register_skills(mcp)
_register_custom(mcp)


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
def notify_ui(
    event: Annotated[str, Field(description="Event name the UI should react to.")],
    data: Annotated[dict | str | None, Field(description="Optional payload.")] = None,
) -> ToolResult:
    """Post a notification for the UI. The UI consumes it by calling poll_agent_notifications."""
    _queue_append(event, data)
    return ToolResult(content=[TextContent(type="text", text="ok")])


@mcp.tool()
def poll_agent_notifications() -> ToolResult:
    """Return all pending agent notifications in order and clear the queue.
    Call from the UI via window.app.callServerTool('poll_agent_notifications', {})."""
    items = _queue_drain()
    return ToolResult(content=[TextContent(type="text", text=json.dumps(items))])


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

    UI→agent (MCP ext-apps; async, return Promises — params MUST be structured, not bare strings):
      window.app.updateModelContext({content: [{type: "text", text: "..."}]})
        attaches state for the next turn (no immediate model response).
      window.app.sendMessage({role: "user", content: [{type: "text", text: "..."}]})
        posts a chat reply (populates the user input box).

    Agent→UI via notify_ui: call notify_ui(event, data) from the agent; the UI registers
      app.ontoolresult to receive result._meta.event and result._meta.data.

    UI-defined tools the agent can call: register app.onlisttools (advertise) and
      app.oncalltool (handle). The host relays agent invocations to the UI.
    """
    return ToolResult(
        content=[TextContent(type="text", text="Content displayed to user.")],
        meta={"html": html_fragment},
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()
