---
description: How lustereczko's UI and the agent communicate — updateModelContext, sendMessage, notify_ui + poll_agent_notifications (file-queue polling), the log back-channel, and custom backend tools. NOTE: oncalltool/onlisttools and the ontoolresult/_meta path are broken on Claude desktop — do not use.
---

# UI ↔ Agent Communication

## Overview

MCP Apps protocol is limited to sendMessage and updateModelContext, and these provide for a very limited experience for the user. This document discusses what custom information passing techniques the agent can implement, and provides guidance on when to use it.

Generally:
- pick the simplest protocol that handles all app use cases and try to only use that protocol throughout. Try not to mix protocols, to keep the generated app simple. Exception: logging can be mixed with all protocols.

## MCP App

window.app.updateModelContext() — this in most host applications is implemented as silent context insertion into the chat which gets added when user enters the next prompt. In our example, we used it to track user actions. This is only useful for the simplest of interactions.

window.app.sendMessage() - this results in the user prompt input box being populated with whatever the message content is. User then gets to decide if it needs editing and when to submit that prompt into chat. It is rather confusing to the user for large inputs, but could be useful if the app was about choosing from a complicated set of options, and you want to clearly communicate back to the agent all selections user has made. Some practitioners also suggest using it to request that agent calls a specified tool with specific parameters (or allowing agent to decide on what parameters to pass). This can work for very simple interactions, where user needs to inspect every step of UI to agent communication, or where the workflow is simple and fixed on UI (user chooses options) -> agent (matches options to some external action) -> external service/tool call.

### oncalltool — do not use

`oncalltool`/`onlisttools` require the Claude desktop host to relay the agent's `tools/call` request from the agent's MCP connection to the UI's SSE connection. This relay is not implemented in Claude desktop 1.0.0. Setting `oncalltool` triggers a capability negotiation that fails with "Client does not support tool capability", and may also break `callServerTool` for the remainder of the session.

**Do not attempt to implement this mechanism.** Use `notify_ui` + `poll_agent_notifications` for agent→UI signaling instead (see section below).

For UI→agent communication, `sendMessage` and `updateModelContext` remain the supported paths.

### notify_ui — agent→UI signaling via file queue + polling

The `_meta`/`ontoolresult` path (spec: `ui/notifications/tool-result`) is not consistently dispatched by Claude desktop — the host does not route tool results to the UI for tools other than `display_ui_to_user`, regardless of `AppConfig(resource_uri=...)` metadata. **Use the polling mechanism instead.**

`notify_ui` enqueues an event to a file-backed queue (`notifications.json`, `fcntl`-locked). The UI drains it by calling `poll_agent_notifications` on a timer.

**What the agent puts on the queue:**

```python
notify_ui(event="my-event", data={"key": "value"})
# Appends to queue: {"event": "my-event", "data": {"key": "value"}}
```

**What `poll_agent_notifications` returns** (as `content[0].text`, JSON-encoded):

```json
[
  {"event": "my-event", "data": {"key": "value"}},
  {"event": "another-event", "data": null}
]
```

Returns all pending items in FIFO order and clears the queue atomically. Returns `[]` when the queue is empty.

**Minimal UI polling code:**

```js
function normalize(d) {
  // data may arrive as a pre-serialized string depending on FastMCP version
  if (d == null || typeof d !== 'string') return d;
  try { return JSON.parse(d); } catch(e) { return d; }
}

function poll() {
  window.app.callServerTool({ name: 'poll_agent_notifications', arguments: {} })
    .then(result => {
      const text = result?.content?.[0]?.text ?? result;
      const items = JSON.parse(typeof text === 'string' ? text : JSON.stringify(text));
      items.forEach(evt => {
        const data = normalize(evt.data);
        handleEvent(evt.event, data);   // your handler
      });
    })
    .catch(err => console.warn('poll error', err))
    .finally(() => setTimeout(poll, 1500));
}

setTimeout(poll, 500);   // start after short delay for app.connect()
```

**Notes:**
- `callServerTool` takes `{ name, arguments }` — not positional args.
- Always use `.finally(() => setTimeout(poll, N))` so polling continues after errors.
- 1500 ms is a safe interval; the call itself adds latency on top.
- `data` values may deserialize as strings on some FastMCP versions — always normalize before use.
- The queue is a flat JSON file at `logs/notifications.json`; cross-process safe via `fcntl.LOCK_EX`.

Full App handler reference: [apps.extensions.modelcontextprotocol.io/api/classes/app.App.html](https://apps.extensions.modelcontextprotocol.io/api/classes/app.App.html)

## Adding custom backend tools for the agent

Unless the data is really simple, agent should avoid mixing data and display code in the UI app. It is best to provide a backend call for the app. This is done by adding a custom tool (via add_custom_tool). UI can then retrieve the data via call custom tool tool call (window.app.callServerTool("run_custom_tool", ...)). 

Example — read a local file:

```python
def run():
    return open("/absolute/path/to/file.txt").read()
```

Use absolute paths. The server's working directory is not predictable.

Note, some hosts start multiple processes, and Agent ends up talking to one instance, while UI is polling another. It is necessary to coortinate messages with a inter process shared resource, ie a file. Remember to write lock the resource access when writing so it doesn't get corrupted.

## The log back-channel

Agent should instrument the app with debug info. UI can call tool write_server_log to pass debug information about its state and the agent can then call tail_server_log to read the UI state and troubleshoot. Note, host capabilities negotiated at app startup are already instrumented to be written to the log.

