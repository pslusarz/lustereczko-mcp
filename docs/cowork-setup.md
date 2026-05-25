# Using lustereczko with Claude Desktop (Cowork mode)

## Compatibility

| Host | MCP App UI works? |
|---|---|
| Claude Desktop — Cowork mode | ✅ Yes |
| Claude Desktop — Claude Code tab | ❌ No |
| VS Code Claude extension | ❌ No |
| Claude Code CLI | ❌ No |

MCP App UI (`text/html;profile=mcp-app`) is a FastMCP extension that is only surfaced by Cowork mode. The MCP server itself will install and connect in any host, but the panel will never appear outside Cowork.

## Requirements

- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/) (used for dependency management and running the server)

## Installation

Clone the repo, then install dependencies:

```bash
cd lustereczko-mcp/mcp
uv sync
```

## Registering with Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (create it if it doesn't exist):

```json
{
  "mcpServers": {
    "lustereczko": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/absolute/path/to/lustereczko-mcp/mcp",
        "lustereczko"
      ]
    }
  }
}
```

Replace `/absolute/path/to/lustereczko-mcp/mcp` with the real path on your machine. Use `pwd` inside `lustereczko-mcp/mcp` if you're unsure.

Restart Claude Desktop after saving.

## Verifying the connection

Open Cowork mode. In the MCP panel (hammer icon), `lustereczko` should appear as connected. If it shows an error, check `lustereczko-mcp/logs/server.log` — the server logs every call and startup error there.

## Picking up the skill

Copy or symlink the `skills/lustereczko-recipies` directory into Claude's skills folder:

```bash
cp -r lustereczko-mcp/skills/lustereczko-recipies \
  ~/Library/Application\ Support/Claude/skills/
```

The skill teaches Claude how to structure fragments, inject external scripts safely, and debug the `window.app` bridge.

## The window.app bridge

Inside any fragment rendered by `display_ui_to_user`, two async methods are available:

```js
// Attach context to Claude's next turn (no immediate response triggered)
window.app.updateModelContext({ content: [{ type: "text", text: "..." }] })

// Post a message as if the user typed it (triggers a response immediately)
window.app.sendMessage({ role: "user", content: [{ type: "text", text: "..." }] })
```

Both return Promises. **Parameters must be structured objects** — bare strings cause a silent failure (`Cannot read properties of undefined (reading 'filter')`).

When using `updateModelContext`, the context is attached to the user's *next* message — Claude won't see it until the user sends something.

## Common pitfalls

**`window.app` is undefined** — the fragment is likely inside an `<iframe srcdoc>`, which inherits a strict CSP that blocks the bridge script. Render markup directly; never use `<iframe srcdoc>`.

**External scripts race with inline scripts** — `<script src="...">` in the fragment is unreliable because subsequent inline scripts may execute before the external one loads. Inject dynamically instead:

```js
const s = document.createElement('script');
s.src = 'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js';
s.onload = () => { /* init here */ };
document.head.appendChild(s);
```

**Allowed external origins**: `cdn.jsdelivr.net`, `unpkg.com`, `*.tile.openstreetmap.org`. All other external resources are blocked by CSP.

**Server not appearing in Cowork**: make sure you're in Cowork mode, not the Claude Code tab of Claude Desktop. They share the app but have separate MCP contexts.

## Debugging

See the `lustereczko-recipies` skill (`SKILL.md`) for a drop-in debug harness that surfaces `window.app` bridge errors inside the rendered panel itself.
