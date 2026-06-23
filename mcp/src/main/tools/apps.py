import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Annotated

from pydantic import Field
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent

from .custom import _TOOLS_DIR

_SCRATCHPAD_DIR = Path(__file__).parents[4] / "server-scratchpad"
_APPS_DIR = _SCRATCHPAD_DIR / "apps"
_CURRENT_UI_FILE = _SCRATCHPAD_DIR / "current_ui.html"

_APP_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_DIR_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{4})-(.+)$")


def _parse_dir_name(dir_name: str) -> tuple[str, str, str] | None:
    """Parse a directory name into (date, hhmm, app_name), or None if not a valid app dir."""
    m = _DIR_RE.match(dir_name)
    return (m.group(1), m.group(2), m.group(3)) if m else None


def _app_dir_for_name(name: str) -> Path | None:
    """Return the directory for app *name*, or None if not found."""
    if not _APPS_DIR.exists():
        return None
    matches = [
        d for d in _APPS_DIR.iterdir()
        if d.is_dir() and (p := _parse_dir_name(d.name)) and p[2] == name
    ]
    return matches[0] if matches else None


def _unique_app_name(name: str) -> str:
    """Return *name* unchanged, or *name*-2, *name*-3, etc. if an app by that name already exists."""
    if not _APPS_DIR.exists():
        return name
    existing = {
        p[2]
        for d in _APPS_DIR.iterdir()
        if d.is_dir() and (p := _parse_dir_name(d.name))
    }
    candidate, counter = name, 2
    while candidate in existing:
        candidate = f"{name}-{counter}"
        counter += 1
    return candidate


def _make_dir_name(name: str) -> str:
    return f"{datetime.now().strftime('%Y-%m-%d-%H%M')}-{name}"


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def save_current_app(  # pyright: ignore[reportUnusedFunction]
        name: Annotated[str, Field(description="Short identifier for the app (alphanumeric, hyphens, underscores, max 64 chars). Do NOT include a date — it is added automatically. If a saved app with this name already exists, a numeric suffix is appended (e.g. my-app-2); the final assigned name is returned in the result.")],
        catalog_description: Annotated[str, Field(description="One-line summary of what the app does, shown in list_saved_apps.")],
        agent_context: Annotated[str, Field(description="Full operating context returned to the agent on load: what the app does, special tuning, techniques used, gotchas, and any bidirectional messaging protocol. Brief and terse.")],
        tool_names: Annotated[list[str], Field(description="Names of custom tools to bundle with this app")] = [],
    ) -> ToolResult:
        """Save the current app state (UI + custom tools) for later reload with load_app."""
        if not _APP_NAME_RE.match(name):
            raise ValueError(f"Invalid app name {name!r}: must be 1-64 alphanumeric/hyphen/underscore characters.")
        if not _CURRENT_UI_FILE.exists():
            raise ValueError("No UI has been displayed yet. Call display_ui_to_user before saving an app.")

        assigned = _unique_app_name(name)
        app_dir = _APPS_DIR / _make_dir_name(assigned)
        app_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy(_CURRENT_UI_FILE, app_dir / "frontend.html")
        (app_dir / "catalog_description.txt").write_text(catalog_description)
        (app_dir / "agent_context.md").write_text(agent_context)

        if tool_names:
            missing = [t for t in tool_names if not (_TOOLS_DIR / f"{t}.py").exists()]
            if missing:
                raise ValueError(f"Custom tools not found: {', '.join(missing)}")
            tools_dir = app_dir / "tools"
            tools_dir.mkdir(exist_ok=True)
            for tool_name in tool_names:
                shutil.copy(_TOOLS_DIR / f"{tool_name}.py", tools_dir / f"{tool_name}.py")

        return ToolResult(content=[TextContent(type="text", text=f"App saved as '{assigned}'.")])

    @mcp.tool()
    def load_app(  # pyright: ignore[reportUnusedFunction]
        name: Annotated[str, Field(description="App name as returned by list_saved_apps (without date).")],
    ) -> ToolResult:
        """Returns a full blueprint of the app to the agent, with instructions on how to bootstrap it."""
        app_dir = _app_dir_for_name(name)
        if app_dir is None:
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
            "tools": {
                f.stem: f.read_text()
                for f in sorted((app_dir / "tools").glob("*.py"))
            } if (app_dir / "tools").exists() else {},
        }
        return ToolResult(content=[TextContent(type="text", text=json.dumps(payload, indent=2))])

    @mcp.tool()
    def list_saved_apps() -> ToolResult:  # pyright: ignore[reportUnusedFunction]
        """List all saved apps sorted newest first. Returns name, saved_at, and catalog_description for each."""
        if not _APPS_DIR.exists():
            return ToolResult(content=[TextContent(type="text", text="[]")])
        apps = []
        for d in sorted(_APPS_DIR.iterdir(), reverse=True):
            parsed = _parse_dir_name(d.name)
            catalog = d / "catalog_description.txt"
            if d.is_dir() and parsed and catalog.exists():
                date_str, hhmm, app_name = parsed
                apps.append({
                    "name": app_name,
                    "saved_at": f"{date_str} {hhmm[:2]}:{hhmm[2:]}",
                    "catalog_description": catalog.read_text(),
                })
        return ToolResult(content=[TextContent(type="text", text=json.dumps(apps, indent=2))])
