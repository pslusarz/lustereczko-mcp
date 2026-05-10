---
name: mcp-dynamic-ui-debug
description: Adds an in-page debug log + per-call diagnostics when rendering HTML fragments via the dynamic-ui MCP server's display_ui_to_user tool. Use when a fragment renders blank, scripts seem inert, or window.app calls (sendMessage / updateModelContext) fail silently.
---

# MCP dynamic-ui debug logger

When a fragment sent to `display_ui_to_user` misbehaves (empty canvas, no chat reply from a click handler, silent promise rejection), inject this lightweight debug harness into the fragment itself. It does not require server changes.

## What to inject

Add these two pieces to the fragment you pass to `display_ui_to_user`:

1. A visible log panel:

```html
<pre id="mcp-log" style="margin:8px 0 0;padding:8px;background:#111;color:#0f0;font:12px/1.4 monospace;max-height:240px;overflow:auto;border-radius:6px">log:</pre>
```

2. A logger that mirrors to the panel and the console, plus capture for uncaught errors and rejected promises:

```html
<script>
(function(){
  function log(msg){
    var el = document.getElementById("mcp-log");
    var line = typeof msg === "string" ? msg : JSON.stringify(msg);
    if (el) el.textContent += "\n" + line;
    console.log("[mcp]", line);
  }
  window.mcpLog = log;
  window.addEventListener("error", function(e){ log("error: " + (e.message || e)); });
  window.addEventListener("unhandledrejection", function(e){
    log("unhandled: " + (e.reason && e.reason.message || e.reason));
  });
  // Probe the host bridge.
  log("app = " + (typeof window.app));
  if (window.app) {
    log("app keys: " + Object.keys(window.app).join(","));
    log("sendMessage = " + typeof window.app.sendMessage);
    log("updateModelContext = " + typeof window.app.updateModelContext);
  }
})();
</script>
```

## Wrapping window.app calls

When invoking `sendMessage` / `updateModelContext` from your own handlers, wrap them so the log captures both shape and outcome. Note the **structured params** required by ext-apps >=1.7 — bare strings cause the host to throw `Cannot read properties of undefined (reading 'filter')`:

```js
function callApp(name, params){
  window.mcpLog(name + " <- " + JSON.stringify(params));
  try {
    var r = window.app[name](params);
    if (r && r.then) r.then(
      function(v){ window.mcpLog(name + " ok: " + JSON.stringify(v)); },
      function(e){ window.mcpLog(name + " err: " + (e && e.message ? e.message : e)); }
    );
    return r;
  } catch(e){
    window.mcpLog(name + " threw: " + (e && e.message ? e.message : e));
    throw e;
  }
}

// Usage:
callApp("sendMessage", { role: "user", content: [{ type: "text", text: "[click] foo" }] });
callApp("updateModelContext", { content: [{ type: "text", text: "lastSelected: foo" }] });
```

## Reading the output

After triggering the suspect interaction, ask the user to paste the contents of the green log panel. Common signals:

- `app = undefined` -> bridge JS never ran. The fragment likely came in via `<iframe srcdoc>`, which inherits a strict CSP and blocks inline scripts. Inline the markup directly instead.
- `sendMessage err: MCP error -32000: Cannot read properties of undefined (reading 'filter')` -> params shape is wrong. Use `{role, content:[{type:"text", text}]}`.
- No log lines at all after a click -> the handler isn't bound. Verify the script ran (the `app keys` line should appear once on render).

## When to remove

Strip the log panel + script before final delivery. They are diagnostic only and bloat the rendered fragment.

## Metadata

Preamble: This skill is part of the Copilot Pincers. It can be updated by installing the latest version from the following location:
origin: gitlab.com/carfax/product-engineering/core-engineering/agentic-workflows/skills/mcp-dynamic-ui-debug

version: 0.1.0
