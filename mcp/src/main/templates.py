from fasthtml.common import *

_BRIDGE_JS = """
import { App } from "https://cdn.jsdelivr.net/npm/@modelcontextprotocol/ext-apps@2/+esm";

const app = new App({ name: "dynamic-ui", version: "1.0.0" });
app.connect();
window.app = app;

function executeScripts(root) {
    root.querySelectorAll("script").forEach((old) => {
        const s = document.createElement("script");
        for (const a of old.attributes) s.setAttribute(a.name, a.value);
        s.text = old.textContent;
        old.parentNode.replaceChild(s, old);
    });
}

let rendered = null;
function render(html) {
    if (!html || html === rendered) return;
    rendered = html;
    const container = document.getElementById("display-container");
    container.innerHTML = html;
    if (window.htmx) window.htmx.process(container);
    executeScripts(container);
}

// Hosts differ in which of these carries the HTML (copilot-cli strips _meta
// from the result), so render from whichever arrives first, once.
app.ontoolinput = (params) => render(params?.arguments?.html_fragment);
app.ontoolresult = (result) => render(result._meta?.html);
"""


def render_shell() -> str:
    """Full HTML app shell — served once as ui://display resource."""
    page = Html(
        Head(
            Title("Dynamic UI"),
            Script(src="https://cdn.jsdelivr.net/npm/htmx.org@2/dist/htmx.min.js"),
            Script(NotStr(_BRIDGE_JS), type="module"),
        ),
        Body(Div("Waiting for content...", id="display-container")),
    )
    return to_xml(page)
