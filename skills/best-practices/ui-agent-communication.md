---
description: How lustereczko's UI and the agent communicate — updateModelContext, sendMessage, the log back-channel, and custom backend tools.
---

# UI ↔ Agent Communication

## Overview

MCP Apps protocol is limited to sendMessage and updateModelContext, and these provide for a very limited experience for the user. This document discusses what custom information passing techniques the agent can implement, and provides guidance on when to use it.

Generally:
- pick the simplest protocol that handles all app use cases and try to only use that protocol throughout. Try not to mix protocols, to keep the generated app simple. Exception: logging can be mixed with all protocols.

## MCP App

window.app.updateModelContext() — this in most host applications is implemented as silent context insertion into the chat which gets added when user enters the next prompt. In our example, we used it to track user actions. This is only useful for the simplest of interactions.

window.app.sendMessage() - this results in the user prompt input box being populated with whatever the message content is. User then gets to decide if it needs editing and when to submit that prompt into chat. It is rather confusing to the user for large inputs, but could be useful if the app was about choosing from a complicated set of options, and you want to clearly communicate back to the agent all selections user has made. Some practitioners also suggest using it to request that agent calls a specified tool with specific parameters (or allowing agent to decide on what parameters to pass). This can work for very simple interactions, where user needs to inspect every step of UI to agent communication, or where the workflow is simple and fixed on UI (user chooses options) -> agent (matches options to some external action) -> external service/tool call.

### oncalltool — UI-defined tools the agent can call

The UI can expose tools back to the agent by implementing two handlers: `onlisttools` (advertises available tools) and `oncalltool` (handles invocations). This is the reverse direction of `window.app.callServerTool()`.

```js
// Advertise tools to the host/agent
app.onlisttools = async (params, extra) => {
  return {
    tools: [
      { name: "my_tool", description: "...", inputSchema: { type: "object", properties: { value: { type: "string" } } } }
    ]
  };
};

// Handle invocations from the agent
app.oncalltool = async (params, extra) => {
  // params.name      — string, tool name the agent called
  // params.arguments — Record<string, unknown> | undefined
  if (params.name === "my_tool") {
    const result = doSomething(params.arguments?.value);
    return { content: [{ type: "text", text: String(result) }] };
  }
  return { content: [{ type: "text", text: "Unknown tool" }], isError: true };
};
```

`oncalltool` must return a `CallToolResult`:
- `content`: array of content blocks (`{ type: "text", text: string }` etc.)
- `isError`: optional boolean

This mechanism can be used to allow the agent to dynamically replace a part of the UI. Best practice here is to keep it simple and stick to htmx conventions.

## Adding custom backend tools for the agent

Unless the data is really simple, agent should avoid mixing data and display code in the UI app. It is best to provide a backend call for the app. This is done by adding a custom tool (via add custom tool). UI can then retrieve the data via call custom tool tool call (window.app.callServerTool("run_custom_tool", ...)). 

Example — read a local file:

```python
def run():
    return open("/absolute/path/to/file.txt").read()
```

Use absolute paths. The server's working directory is not predictable.

## The log back-channel

Agent should instrument the app with debug info. UI can call tool write_server_log to pass debug information about its state and the agent can then call tail_server_log to read the UI state and troubleshoot. Note, host capabilities negotiated at app startup are already instrumented to be written to the log.

## Message stream emulation (not yet implemented)

Most flexible is the use of two custom tools ui_to_agent(message, [params]) and agent_to_ui(message, [params]). Both sides need to implement polling, and decide how to respond to messages. While polling on the UI side is not a problem, it is no different than ontoolcall mechanism above that is already provided by MCP Apps. Polling on the agent side could be really powerful (superseding any "mcp sampling" functionality), if host's agent was able to sustain it. This is speculative, but noting it here so we can get back to experimenting with it.