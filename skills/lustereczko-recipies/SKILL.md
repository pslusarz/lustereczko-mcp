---
name: lustereczko
description: Recipes for working with the lustereczko dynamic-ui MCP server. Use when rendering HTML fragments via display_ui_to_user — debugging blank renders, wiring up window.app callbacks, or diagnosing silent failures.
---

# Lustereczko recipes

## Recipes

| Situation | Recipe |
|-----------|--------|
| Debugging the UI is called on by the user, or user indicates an issue with the generated UI, ie the fragment renders blank, scripts inert, or `window.app` calls fail silently | [UI debug logger](recipes/ui-debug.md) |
| Need to know what the host supports before building a fragment, or user wants to inspect capabilities/context/version at runtime | [Host capabilities inspector](recipes/host-capabilities.md) |
