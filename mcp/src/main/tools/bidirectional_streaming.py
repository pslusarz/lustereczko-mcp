import fcntl
import json
from pathlib import Path
from typing import Annotated

from pydantic import Field
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent

_LOG_DIR = Path(__file__).parents[4] / "logs"

_UI_MESSAGES_FILE    = _LOG_DIR / "ui_messages.json"     # agent → UI (UI reads)
_AGENT_MESSAGES_FILE = _LOG_DIR / "agent_messages.json"  # UI → agent (agent reads)


def _queue_append(queue_file: Path, event: str, data) -> None:
    queue_file.touch(exist_ok=True)
    with open(queue_file, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        content = f.read().strip()
        items = json.loads(content) if content else []
        items.append({"event": event, "data": data})
        f.seek(0)
        f.truncate()
        json.dump(items, f)


def _queue_drain(queue_file: Path) -> list:
    queue_file.touch(exist_ok=True)
    with open(queue_file, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        content = f.read().strip()
        items = json.loads(content) if content else []
        f.seek(0)
        f.truncate()
        json.dump([], f)
    return items


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def notify_ui(
        event: Annotated[str, Field(description="Event name the UI should react to.")],
        data: Annotated[dict | str | None, Field(description="Optional payload.")] = None,
    ) -> ToolResult:
        """Post a notification for the UI. The UI consumes it by calling poll_ui_messages."""
        _queue_append(_UI_MESSAGES_FILE, event, data)
        return ToolResult(content=[TextContent(type="text", text="ok")])

    @mcp.tool()
    def poll_ui_messages() -> ToolResult:
        """Return all pending agent→UI notifications in order and clear the queue.
        Call from the UI via window.app.callServerTool('poll_ui_messages', {})."""
        items = _queue_drain(_UI_MESSAGES_FILE)
        return ToolResult(content=[TextContent(type="text", text=json.dumps(items))])

    @mcp.tool()
    def notify_agent(
        event: Annotated[str, Field(description="Event name the agent should react to.")],
        data: Annotated[dict | str | None, Field(description="Optional payload.")] = None,
    ) -> ToolResult:
        """Post a message from the UI to the agent queue. The agent consumes it by calling poll_agent_messages."""
        _queue_append(_AGENT_MESSAGES_FILE, event, data)
        return ToolResult(content=[TextContent(type="text", text="ok")])

    @mcp.tool()
    def poll_agent_messages() -> ToolResult:
        """Return all pending UI→agent messages in order and clear the queue."""
        items = _queue_drain(_AGENT_MESSAGES_FILE)
        return ToolResult(content=[TextContent(type="text", text=json.dumps(items))])
