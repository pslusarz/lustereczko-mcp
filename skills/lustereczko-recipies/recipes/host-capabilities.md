---
description: Inspect host capabilities, context, and version exposed by the MCP ext-apps bridge. Use when you need to know what the host supports before building a fragment.
---

# Host capabilities inspector

Call `display_ui_to_user` with this fragment to render a live inspector panel. It reads `getHostCapabilities()`, `getHostContext()`, and `getHostVersion()` from `window.app` on button click — no load-time JS, so timing issues with the bridge are avoided.

## Fragment to send

```html
<style>
button { padding: 6px 13px; border-radius: 6px; border: none; font-size: 12px; font-weight: 500; cursor: pointer; margin-right: 6px; }
pre { background: #0f172a; color: #7dd3fc; font: 11px/1.6 Menlo, monospace; border-radius: 8px; padding: 12px; max-height: 340px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; margin-top: 12px; }
</style>
<div style="padding:16px;font-family:system-ui,sans-serif">
  <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:4px">
    <button onclick="show('capabilities', window.app?.getHostCapabilities())" style="background:#6366f1;color:#fff">Capabilities</button>
    <button onclick="show('context', window.app?.getHostContext())" style="background:#0284c7;color:#fff">Context</button>
    <button onclick="show('version', window.app?.getHostVersion())" style="background:#7c3aed;color:#fff">Version</button>
    <button onclick="showAll()" style="background:#0f172a;color:#fff">All</button>
    <button onclick="sendToChat()" style="background:#059669;color:#fff">Send to chat ↑</button>
    <button onclick="sendToLog()" style="background:#b45309;color:#fff">Send to log ↑</button>
  </div>
  <pre id="out">press a button...</pre>
</div>
<script>
var last = null;
function show(label, val) {
  last = {}; last[label] = val ?? null;
  document.getElementById('out').textContent = JSON.stringify(last, null, 2);
}
function showAll() {
  last = {
    capabilities: window.app?.getHostCapabilities() ?? null,
    context:      window.app?.getHostContext()      ?? null,
    version:      window.app?.getHostVersion()      ?? null
  };
  document.getElementById('out').textContent = JSON.stringify(last, null, 2);
}
function sendToChat() {
  if (!last) { document.getElementById('out').textContent = 'Nothing scanned yet.'; return; }
  window.app.sendMessage({ role: 'user', content: [{ type: 'text', text: 'Host info:\n```json\n' + JSON.stringify(last, null, 2) + '\n```' }] });
}
async function sendToLog() {
  if (!last) { document.getElementById('out').textContent = 'Nothing scanned yet.'; return; }
  await window.app.callServerTool({ name: 'write_server_log', arguments: { message: last } });
  document.getElementById('out').textContent += '\n\n[logged to server — use tail_server_log to read]';
}
</script>
```

## Reading the output

- **`capabilities`** — what the host supports: `openLinks`, `downloadFile`, `serverTools`, `sandbox.csp` (allowed fetch domains), `updateModelContext`, `message`. Use this before calling any `window.app` method to check it's available.
- **`context`** — runtime environment: `theme`, `styles.variables` (CSS design tokens), `displayMode`, `containerDimensions`, `locale`, `timeZone`, `platform`, `deviceCapabilities`.
- **`version`** — host name and version string.

Key things to check:

- `capabilities.sandbox.csp.connectDomains` — only these domains are reachable via `fetch` or htmx. Requests to anything else silently kill the render.
- `context.theme` — `"light"` or `"dark"`, use to conditionally apply styles.
- `context.styles.variables` — full Anthropic design token set, usable as CSS `var(--color-text-primary)` etc. if you want native look.
- `capabilities.updateModelContext` — confirms `window.app.updateModelContext()` is available before calling it.

## Metadata

version: 0.1.0
