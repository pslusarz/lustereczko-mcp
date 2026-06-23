import json
import re
import shutil
from datetime import date
from pathlib import Path
from typing import Annotated

from pydantic import Field
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent

_SCRATCHPAD_DIR = Path(__file__).parents[4] / "server-scratchpad"
_APPS_DIR = _SCRATCHPAD_DIR / "apps"
_CURRENT_UI_FILE = _SCRATCHPAD_DIR / "current_ui.html"

_APP_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def canonical_app_name(name: str) -> str:
    if not _APP_NAME_RE.match(name):
        raise ValueError(f"Invalid app name {name!r}: must be 1-64 alphanumeric/hyphen/underscore characters.")
    return f"{date.today().isoformat()}-{name}"


def _app_dir(canonical_name: str) -> Path:
    return _APPS_DIR / canonical_name


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def save_current_app(  # pyright: ignore[reportUnusedFunction]
        name: Annotated[str, Field(description="Short identifier for the app (alphanumeric, hyphens, underscores, max 64 chars)")],
        catalog_description: Annotated[str, Field(description="One-line summary of what the app does, shown in list_saved_apps.")],
        agent_context: Annotated[str, Field(description="Full operating context returned to the agent on load: what the app does, special tuning, techniques used, gotchas, and any bidirectional messaging protocol. Brief and terse.")],
        tool_names: Annotated[list[str], Field(description="Names of custom tools to bundle with this app")] = [],
    ) -> ToolResult:
        """Save the current app state (UI + custom tools) for later reload with load_app."""
        if not _CURRENT_UI_FILE.exists():
            raise ValueError("No UI has been displayed yet. Call display_ui_to_user before saving an app.")

        app_dir = _app_dir(canonical_app_name(name))
        app_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy(_CURRENT_UI_FILE, app_dir / "frontend.html")
        (app_dir / "catalog_description.txt").write_text(catalog_description)
        (app_dir / "agent_context.md").write_text(agent_context)

        return ToolResult(content=[TextContent(type="text", text=f"App '{name}' saved to {app_dir.name}/")])

    @mcp.tool()
    def load_app(  # pyright: ignore[reportUnusedFunction]
        name: Annotated[str, Field(description="Canonical app name as returned by list_saved_apps, e.g. '2026-06-23-my-app'.")],
    ) -> ToolResult:
        """Returns a full blueprint of the app to the agent, with instructions on how to bootstrap it."""
        app_dir = _app_dir(name)
        if not app_dir.is_dir():
            raise ValueError(f"No saved app '{name}'. Use list_saved_apps to see available apps.")
        payload = {
            "instructions": (
                "1. Re-register any tools in the tools dict via add_custom_tool. "
                "2. If the app uses bidirectional streaming, generate a fresh channel_id "
                "(e.g. f\"ch-{int(time.time()*1000)}\") and replace the old hardcoded "
                "channel_id in the HTML before proceeding — stale channel files may contain "
                "leftover messages. "
                "3. Call display_ui_to_user with the (patched) frontend HTML. "
                "4. Use agent_context as your operating context for this session."
            ),
            "agent_context": (app_dir / "agent_context.md").read_text(),
            "frontend": (app_dir / "frontend.html").read_text(),
            "tools": {},
        }
        return ToolResult(content=[TextContent(type="text", text=json.dumps(payload, indent=2))])

    @mcp.tool()
    def list_saved_apps() -> ToolResult:  # pyright: ignore[reportUnusedFunction]
        """List all saved apps sorted by date, newest first. Returns name and description for each."""
        if not _APPS_DIR.exists():
            return ToolResult(content=[TextContent(type="text", text="[]")])
        apps = []
        for d in sorted(_APPS_DIR.iterdir(), reverse=True):
            catalog = d / "catalog_description.txt"
            if d.is_dir() and catalog.exists():
                apps.append({"name": d.name, "catalog_description": catalog.read_text()})
        return ToolResult(content=[TextContent(type="text", text=json.dumps(apps, indent=2))])
