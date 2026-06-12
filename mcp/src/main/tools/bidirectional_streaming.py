import fcntl
import json
import re
from pathlib import Path
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent
from pydantic import Field

_LOG_DIR = Path(__file__).parents[4] / "logs"
_CHANNELS_DIR = _LOG_DIR / "channels"

# Strict allowlist: alphanumeric, hyphens, underscores, 1-64 chars.
# Prevents path traversal and keeps filenames predictable.
_CHANNEL_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _channel_file(channel_id: str, direction: str) -> Path:
    """Return the queue file for *direction* ('ui' or 'agent') on *channel_id*.

    Raises ValueError if channel_id fails validation so callers get a clear
    error rather than a silent path-traversal.
    """
    if not _CHANNEL_RE.match(channel_id):
        raise ValueError(
            f"Invalid channel_id {channel_id!r}: "
            "must be 1-64 alphanumeric/hyphen/underscore characters."
        )
    _CHANNELS_DIR.mkdir(parents=True, exist_ok=True)
    return _CHANNELS_DIR / f"{direction}_{channel_id}.json"


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
        channel_id: Annotated[
            str,
            Field(
                description=(
                    "Channel identifier. Agent should assign a unique id for each display_ui_to_user call and should hardcode that ID in the UI to be used by both agent and UI. "
                    "Alphanumeric, hyphens and underscores only, 1-64 chars."
                )
            ),
        ],
        data: Annotated[
            dict | str | None, Field(description="Optional payload.")
        ] = None,
    ) -> ToolResult:
        """Post a notification for the UI. The UI consumes it by calling poll_ui_messages."""
        _queue_append(_channel_file(channel_id, "ui"), event, data)
        return ToolResult(content=[TextContent(type="text", text="ok")])

    @mcp.tool()
    def poll_ui_messages(
        channel_id: Annotated[
            str,
            Field(
                description=(
                    "Channel identifier matching the one used in notify_ui. "
                    "Only messages for this channel are returned."
                )
            ),
        ],
    ) -> ToolResult:
        """Return all pending agent→UI notifications in order and clear the queue.

        Call from the UI via:
            window.app.callServerTool('poll_ui_messages', {channel_id: MY_CHANNEL})
        """
        items = _queue_drain(_channel_file(channel_id, "ui"))
        return ToolResult(content=[TextContent(type="text", text=json.dumps(items))])

    @mcp.tool()
    def notify_agent(
        event: Annotated[str, Field(description="Event name the agent should react to.")],
        channel_id: Annotated[
            str,
            Field(
                description=(
                    "Channel identifier assigned when agent generated the UI. Alphanumeric, hyphens and underscores only, 1-64 chars."
                )
            ),
        ],
        data: Annotated[
            dict | str | None, Field(description="Optional payload.")
        ] = None,
    ) -> ToolResult:
        """Post a message from the UI to the agent queue. The agent consumes it by calling poll_agent_messages.
        
    Channel ID protocol — ALWAYS follow this for bidirectional communication:
      1. Generate a channel_id before this call: e.g. f"ch-{int(time.time()*1000)}"
      2. Embed it as a literal constant in the HTML: const MY_CHANNEL = "<channel_id>";
      3. Use it in every notify_ui / poll_agent_messages call on the agent side.
      4. The UI uses MY_CHANNEL in every poll_ui_messages / notify_agent call.
      Each display_ui_to_user call gets a fresh channel_id. Old panels keep their own
      channel and remain fully isolated.
        
        """
        _queue_append(_channel_file(channel_id, "agent"), event, data)
        return ToolResult(content=[TextContent(type="text", text="ok")])

    @mcp.tool()
    def poll_agent_messages(
        channel_id: Annotated[
            str,
            Field(
                description=(
                    "Channel identifier to poll. Both agent and app should poll and write to the same channel. Only messages for this channel are returned."
                )
            ),
        ],
    ) -> ToolResult:
        """Return all pending UI→agent messages in order and clear the queue."""
        items = _queue_drain(_channel_file(channel_id, "agent"))
        return ToolResult(content=[TextContent(type="text", text=json.dumps(items))])
