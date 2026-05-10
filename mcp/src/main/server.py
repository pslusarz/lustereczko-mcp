import logging
from pathlib import Path
from typing import Annotated

from pydantic import Field
from fastmcp import FastMCP
from fastmcp.apps.config import AppConfig, ResourceCSP
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
    "dynamic-ui",
    version="0.1.0",
    instructions=(
        "Render arbitrary HTML in the user's UI panel via display_ui_to_user. "
        "See the tool's description for capabilities, allowed origins, and the window.app API."
    ),
)

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
      window.app.sendMessage({role: "user", content: [{type: "text", text: "..."}]})
        posts a chat reply.
      window.app.updateModelContext({content: [{type: "text", text: "..."}]})
        attaches state for the next turn (no immediate model response).
    htmx is also preloaded. External resources allowed from cdn.jsdelivr.net,
    unpkg.com, and *.tile.openstreetmap.org.
    Avoid <iframe srcdoc>; sandboxed iframes inherit CSP and block inline scripts.
    """
    return ToolResult(
        content=[TextContent(type="text", text="Content displayed to user.")],
        meta={"html": html_fragment},
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()
