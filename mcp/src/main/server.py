import logging
import re
from dataclasses import dataclass
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
        "Use tail_log to inspect server logs when debugging."
    ),
)
_SILENT_TOOLS = {"log_init_result", "tail_log"}


class _ToolLoggingMiddleware(LoggingMiddleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        if context.message.name in _SILENT_TOOLS:
            return await call_next(context)
        return await super().on_call_tool(context, call_next)


mcp.add_middleware(_ToolLoggingMiddleware(logger=logging.getLogger(__name__), include_payloads=True))

@dataclass
class _Recipe:
    slug: str
    name: str
    description: str
    path: Path


def _parse_recipe(path: Path) -> "_Recipe":
    text = path.read_text()
    fm = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if fm:
        fields = {}
        for line in fm.group(1).splitlines():
            k, _, v = line.partition(":")
            if _:
                fields[k.strip()] = v.strip()
        name = fields.get("name", path.stem)
        description = fields.get("description", f"Recipe: {path.stem}")
    else:
        h1 = re.search(r"^# (.+)$", text, re.MULTILINE)
        name = h1.group(1).strip() if h1 else path.stem
        first_para = re.search(r"^(?!#)(.{20,})", text, re.MULTILINE)
        description = first_para.group(1).strip()[:200] if first_para else f"Recipe: {path.stem}"
    return _Recipe(slug=path.stem, name=name, description=description, path=path)


def _register_recipes(recipes_dir: Path) -> None:
    if not recipes_dir.exists():
        return
    for path in sorted(recipes_dir.glob("*.md")):
        recipe = _parse_recipe(path)

        def _make_serve(p: Path):
            def serve() -> str:
                return p.read_text()
            return serve

        mcp.resource(
            f"skill://recipes/{recipe.slug}",
            name=recipe.name,
            description=recipe.description,
            mime_type="text/markdown",
        )(_make_serve(recipe.path))


_RECIPES_DIR = Path(__file__).parents[3] / "skills" / "lustereczko-recipies" / "recipes"
_register_recipes(_RECIPES_DIR)

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
def log_init_result(init_result: dict | None = None) -> ToolResult:
    """Called by the UI app on startup to log McpUiInitializeResult to the server log."""
    import json
    logging.getLogger(__name__).info(
        "McpUiInitializeResult:\n%s", json.dumps(init_result, indent=2)
    )
    return ToolResult(content=[TextContent(type="text", text="Logged.")])


@mcp.tool()
def tail_log(n: Annotated[int, Field(description="Number of lines to return", default=50)] = 50) -> ToolResult:
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
      
    htmx is also preloaded. External resources allowed from cdn.jsdelivr.net,
    unpkg.com, and *.tile.openstreetmap.org.
    Avoid <iframe srcdoc>; sandboxed iframes inherit CSP and block inline scripts.

    Examples: read the skill://recipes/* resources
    (troubleshooting blank renders, silent failures, window.app errors).
    """
    return ToolResult(
        content=[TextContent(type="text", text="Content displayed to user.")],
        meta={"html": html_fragment},
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()
