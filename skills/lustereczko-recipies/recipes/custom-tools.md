---
description: Deploy and call a dynamic Python tool from the UI using add_custom_tool and window.app.callServerTool.
---

# Custom tools recipe

## 1. Deploy the tool

Call `add_custom_tool` with a name and Python source. The code must define `run(**kwargs)`. State persists in module-level variables for the server lifetime.

```json
{
  "name": "counter",
  "code": "value = 0\ndef run(number): global value; value += number; return value"
}
```

## 2. Call from UI

Use `window.app.callServerTool` to invoke `run_custom_tool` directly — no chat round-trip.

```html
<button onclick="add()">+1</button><span id="v">0</span>
<script>
async function add() {
  var r = await window.app.callServerTool({
    name: 'run_custom_tool',
    arguments: { name: 'counter', args: { number: 1 } }
  });
  document.getElementById('v').textContent = r.content[0].text;
}
</script>
```

## Notes

- Custom tools are **in-memory only** — lost on server restart. Re-deploy after restart.
- `run_custom_tool` passes `args` as `**kwargs` to `run()`, so argument names must match.
