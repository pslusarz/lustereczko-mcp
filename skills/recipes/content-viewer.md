---
description: Build a backend-driven content viewer with timeline in a lustereczko UI panel. Use when the task is to display paginated text content (a book, document, or long-form text) with a character/location timeline visualization, driven by Python custom tools on the lustereczko server. Use when user content is too large to embed in the UI directly. 
---

# Lustereczko content viewer recipe

Builds a paginated reader + collapsible SVG timeline entirely driven by server-side Python tools. No content is embedded in the HTML, which frees up agent context from clutter and allows it to focus on technical display issues.

## Architecture

```
Book text (gzip+base64, split across chunk0..N.txt)
    └─► book_get_page          — decompress, split into ~250-word pages
    └─► book_get_chapter_starting_pages  — static chapter→page mapping
    └─► book_characters        — scan pages for character keywords → page lists
    └─► book_locations         — scan pages for location keywords → page lists
           ↓
    display_ui_to_user  ←→  window.app.callServerTool
```

## Multi-worker persistence

The server persists custom tools to `/tmp/lustereczko_tools.json` (with `fcntl` file locking) so tools registered by one process are visible to all others. No action needed — just register your tools with `add_custom_tool` and they will be available to the UI immediately.

## Data ingestion

Large texts must be split into chunk files to avoid log corruption (the server logs tool arguments verbatim). Split gzip+base64 encoded text into 4 files:

```python
import gzip, base64, math
text = open("book.txt").read()
encoded = base64.b64encode(gzip.compress(text.encode())).decode()
size = math.ceil(len(encoded) / 4)
for i in range(4):
    open(f"chunk{i}.txt", "w").write(encoded[i*size:(i+1)*size])
```

The `book_get_page` tool self-heals after server restart by re-reading chunks from disk:

```python
import gzip, base64, os
_pages = None

def _load():
    global _pages
    if _pages is not None: return _pages
    src = "/sessions/<session-id>/mnt/outputs"  # actual mount path
    data = "".join(open(os.path.join(src, f"chunk{i}.txt")).read() for i in range(4))
    text = gzip.decompress(base64.b64decode(data.strip())).decode()
    words = text.split()
    _pages = [" ".join(words[i:i+250]) for i in range(0, len(words), 250)]
    return _pages

def run(page_number=1):
    pages = _load()
    p = int(page_number)
    return pages[p-1] if 1 <= p <= len(pages) else f"Page {p} out of range"
```

## Character/location scanning tools

Same `_load()` pattern, then keyword scan:

```python
import json
CHARACTERS = {
    "Protagonist": ["Name", "Alias"],
    "Antagonist":  ["OtherName"],
}
def run():
    pages = _load()
    return json.dumps({
        name: [i+1 for i, p in enumerate(pages) if any(k in p for k in kws)]
        for name, kws in CHARACTERS.items()
    })
```

Returns `{"Character": [1, 3, 5, 6, ...]}`.

## UI patterns

### Fixed height (required for inline display mode)

`height: 100vh` collapses in inline mode. Use a fixed pixel height:

```css
#app { height: 820px; display: flex; flex-direction: column; }
```

`getHostContext().containerDimensions` gives `{ maxHeight: 5000, width: 736 }`.

### Calling tools from the UI

```js
function call(toolName, args) {
  return window.app.callServerTool({
    name: 'run_custom_tool',
    arguments: { name: toolName, args: args || {} }
  });
}
function getText(r) {
  return r && r.content && r.content[0] && r.content[0].text || '';
}
```

### Timeline: SVG with chapter bands and clickable cursor

Key dimensions for a 736px-wide panel:

```js
var TL = { W: 660, labelW: 108, rowH: 24, headerH: 36 };
var pageW = (TL.W - TL.labelW) / totalPages;
```

Merge consecutive page numbers into single bars:

```js
var j = 0;
while (j < pages.length) {
  var ps = pages[j], pe = pages[j];
  while (j+1 < pages.length && pages[j+1] === pe+1) { j++; pe = pages[j]; }
  // draw one rect from ps to pe
  j++;
}
```

Clicking the timeline jumps to that page:

```js
svg.addEventListener('click', function(e) {
  var relX = e.clientX - e.currentTarget.getBoundingClientRect().left - TL.labelW;
  var p = Math.floor(relX / pageW) + 1;
  if (p >= 1 && p <= totalPages) goToPage(p);
});
```

### Collapsible timeline panel

```html
<div id="timeline-panel" class="open">...</div>
<style>
  #timeline-panel { transition: height 0.25s ease; overflow: hidden; }
  #timeline-panel.open   { height: 210px; }
  #timeline-panel.closed { height: 0; }
</style>
```

## Initialization sequence

```js
call('book_get_chapter_starting_pages').then(function(r) {
  buildChapterNav(JSON.parse(getText(r)));
  return call('book_get_page', { page_number: 1 });
}).then(function(r) {
  showPage(getText(r));
  return Promise.all([call('book_characters'), call('book_locations')]);
}).then(function(res) {
  renderTimeline(JSON.parse(getText(res[0])), JSON.parse(getText(res[1])));
});
```

## Diagnosing tool-not-found errors

If `run_custom_tool` returns "No custom tool named X", the error lists all currently available tools. Use this to verify registration.

## Notes

version: 1.0.0
