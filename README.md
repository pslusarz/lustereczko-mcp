## Lustereczko
Dynamic UI for your generative agent. Your LLM can use it to display HTML interactive UI to the user and modify it on the fly.

**MCP list_tools context footprint: ~3162 tokens.** That is the full cost of adding this server to your agent's context.

This seems modest, and you can use it for modest things like charting data you are currently looking at. But it is also a proof of concept for something much bigger. The agent can write you an app right in the chat. It will be the only app you will ever need because it will be customized to your unique way of doing things, and it will change with you. 

While from the days of the "data analysis" extension in github copilot this was an obvious direction for user interactions, the mainstream industry chose to impose heavyweight protocols and constraints on these interactions. As a result, chat and very klunky UIs are still the norm of how users interact with their LLMs. Lustereczko is here to change that.

## Examples

But let's start small...

**Hello World** — simplest possible display call:

![Hello World](docs/screenshots/hello-world.png)

**Interactive map** — LLM generates a full Leaflet map with 12 Civil War battle markers:

![Interactive map of Missouri Civil War sites](docs/screenshots/interactive-map.png)

**Bidirectional context** — user clicks a marker, `window.app.updateModelContext()` feeds the selection back to the LLM, which then answers questions about it:

![Map with click context](docs/screenshots/map-click-context.png)

It doesn't have to end here. With dynamic tool deployment, you can ask the agent to build you a full blown app — here is an example of an enriched book experience that you can get with one of the recipe skills.

![Rich book experience](docs/screenshots/rich-book-experience.png)

## Installation
Do we really need this? This is a python mcp server, your agent should be able to figure out how to install it locally. While at it, pick up the lustereczko-recipies skill.

> **Claude Desktop (Cowork mode) users:** see [docs/cowork-setup.md](docs/cowork-setup.md) for a step-by-step guide, including compatibility notes — MCP App UI does not work in Claude Code mode or the VS Code CC extension.

## Example prompts
- "Display Civil War battles in Missouri on an interactive map. Pay attention to the battle I select." - will use window.updateModelContext

## How it works
Lustereczko is built on the [MCP Apps protocol](https://apps.extensions.modelcontextprotocol.io/api/), making it compatible with any MCP Apps-compliant host (Claude Desktop, Goose, etc.). At its core, lustereczko takes a UI that the user's LLM has generated and reflects it back to the host.

There had to be some creative adaptation to ellicit a more interactive experience. Because the MCP Apps protocol provides only a foundation, lustereczko adds its own conventions on top to enable rich, dynamic agent↔UI interaction — see the [`best-practices:ui-agent-communication`](skills/best-practices/ui-agent-communication.md) skill for details. There is server log introspection, UI debugging instrumentation, and a dynamic skill system to allow the agent to fix most issues on its own. I would much rather start with a less restrictive protocol, but one has to work within a realistic ecosystem, and in the process of proving why MCP-App protocol can't work, I discovered ways to make it accomplish almost anything that was needed for this rich way of interacting with LLMs.

Why it can't work: it seems many folks have inherent problems with letting LLMs write and execute code. Yes, it can be messy because there are both concerns with security as well as stability of non-deterministic code. Folks have experimentally demonstrated that LLMs have a hard time with complex frameworks like REACT.

Why it works: we keep it local, end encourage best practices through an elaborate skills system. LLMs handle HTMX generated UIs just fine, so we stick to that. Interaction with LLMs does not require complicated UIs, so we can keep it simple on the frontend. For more complex data, we add backend deployment capabilities to avoid mixing content and data and overwhelming frontend code generation. The agent can read the logs, so is able to proceed and troubleshoot most issues on its own. Together this makes a system that is both flexible in what it can express, and stable in having few issues that non-technical users may not be willing to debug. Part of the reason I am convinced it will work is that with user adaptability, we don't really need the complex UIs anymore (think MS Office). The UI can be focused on the task at hand, and regenerated for another task.

Last, but not least, and this is not essential for the LLMs, users do not want the UI to change every time, so there will be a dynamic user generated templating and theme system, where the UI will start at the last point the user saw it (this is still not implemented).

## What is this name
Your LLM knows, so ask it...