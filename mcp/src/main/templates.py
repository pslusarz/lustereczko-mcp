from fasthtml.common import *

_BRIDGE_JS = """
import { App } from "https://cdn.jsdelivr.net/npm/@modelcontextprotocol/ext-apps@latest/+esm";

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

app.ontoolresult = (result) => {
    const meta = result._meta ?? {};
    const container = document.getElementById("display-container");
    if (meta.html) {
        container.innerHTML = meta.html;
        if (window.htmx) window.htmx.process(container);
        executeScripts(container);
    }
};
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
