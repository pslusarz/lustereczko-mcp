import json
import shutil
import uuid

from main.tools.apps import _APPS_DIR, _CURRENT_UI_FILE, _app_dir, canonical_app_name
from main.tools.custom import _TOOLS_DIR


def _save_args(name: str, **overrides):
    return {"name": name, "catalog_description": "catalog", "agent_context": "context", **overrides}


async def test_save_app_without_ui_is_an_error(client):
    _CURRENT_UI_FILE.unlink(missing_ok=True)
    result = await client.call_tool("save_current_app", _save_args(f"test-{uuid.uuid4().hex[:8]}"), raise_on_error=False)
    assert result.is_error


async def test_save_app_captures_frontend(client):
    name = f"test-{uuid.uuid4().hex[:8]}"
    sentinel = f"<p>{uuid.uuid4()}</p>"
    try:
        await client.call_tool("display_ui_to_user", {"html_fragment": sentinel})
        await client.call_tool("save_current_app", _save_args(name))

        assert (_app_dir(canonical_app_name(name)) / "frontend.html").read_text() == sentinel
    finally:
        shutil.rmtree(_app_dir(canonical_app_name(name)), ignore_errors=True)


async def test_save_app_writes_separate_files(client):
    name = f"test-{uuid.uuid4().hex[:8]}"
    catalog = f"catalog-{uuid.uuid4().hex[:8]}"
    context = f"context-{uuid.uuid4().hex[:8]}"
    try:
        await client.call_tool("display_ui_to_user", {"html_fragment": "<p>x</p>"})
        await client.call_tool("save_current_app", _save_args(name, catalog_description=catalog, agent_context=context))

        app_dir = _app_dir(canonical_app_name(name))
        assert (app_dir / "catalog_description.txt").read_text() == catalog
        assert (app_dir / "agent_context.md").read_text() == context
        assert (app_dir / "frontend.html").exists()
    finally:
        shutil.rmtree(_app_dir(canonical_app_name(name)), ignore_errors=True)


async def test_list_saved_apps_empty(client):
    _APPS_DIR.mkdir(parents=True, exist_ok=True)
    for d in _APPS_DIR.iterdir():
        shutil.rmtree(d) if d.is_dir() else d.unlink()
    result = await client.call_tool("list_saved_apps")
    assert json.loads(result.content[0].text) == []


async def test_list_saved_apps_includes_saved_app(client):
    name = f"test-{uuid.uuid4().hex[:8]}"
    catalog = f"catalog-{uuid.uuid4().hex[:8]}"
    try:
        await client.call_tool("display_ui_to_user", {"html_fragment": "<p>x</p>"})
        await client.call_tool("save_current_app", _save_args(name, catalog_description=catalog))

        apps = json.loads((await client.call_tool("list_saved_apps")).content[0].text)
        assert any(a["name"] == canonical_app_name(name) and a["catalog_description"] == catalog for a in apps)
    finally:
        shutil.rmtree(_app_dir(canonical_app_name(name)), ignore_errors=True)


async def test_load_app_returns_context_and_frontend(client):
    name = f"test-{uuid.uuid4().hex[:8]}"
    sentinel_html = f"<p>{uuid.uuid4()}</p>"
    sentinel_context = f"ctx-{uuid.uuid4().hex[:8]}"
    try:
        await client.call_tool("display_ui_to_user", {"html_fragment": sentinel_html})
        await client.call_tool("save_current_app", _save_args(name, agent_context=sentinel_context))

        result = await client.call_tool("load_app", {"name": canonical_app_name(name)})
        payload = json.loads(result.content[0].text)
        assert payload["frontend"] == sentinel_html
        assert payload["agent_context"] == sentinel_context
        assert payload["tools"] == {}
        assert "instructions" in payload
    finally:
        shutil.rmtree(_app_dir(canonical_app_name(name)), ignore_errors=True)


async def test_save_app_copies_tools_into_app_directory(client):
    app_name = f"test-{uuid.uuid4().hex[:8]}"
    tool_name = f"tool-{uuid.uuid4().hex[:8]}"
    tool_code = f"def run(**kwargs): return {uuid.uuid4()!r}"
    try:
        await client.call_tool("add_custom_tool", {"name": tool_name, "code": tool_code})
        await client.call_tool("display_ui_to_user", {"html_fragment": "<p>x</p>"})
        await client.call_tool("save_current_app", _save_args(app_name, tool_names=[tool_name]))

        saved = (_app_dir(canonical_app_name(app_name)) / "tools" / f"{tool_name}.py").read_text()
        assert saved == tool_code
    finally:
        shutil.rmtree(_app_dir(canonical_app_name(app_name)), ignore_errors=True)
        (_TOOLS_DIR / f"{tool_name}.py").unlink(missing_ok=True)


async def test_load_app_returns_tools(client):
    app_name = f"test-{uuid.uuid4().hex[:8]}"
    tool_name = f"tool-{uuid.uuid4().hex[:8]}"
    tool_code = f"def run(**kwargs): return {uuid.uuid4()!r}"
    try:
        await client.call_tool("add_custom_tool", {"name": tool_name, "code": tool_code})
        await client.call_tool("display_ui_to_user", {"html_fragment": "<p>x</p>"})
        await client.call_tool("save_current_app", _save_args(app_name, tool_names=[tool_name]))

        result = await client.call_tool("load_app", {"name": canonical_app_name(app_name)})
        tools = json.loads(result.content[0].text)["tools"]
        assert tools[tool_name] == tool_code
    finally:
        shutil.rmtree(_app_dir(canonical_app_name(app_name)), ignore_errors=True)
        (_TOOLS_DIR / f"{tool_name}.py").unlink(missing_ok=True)


async def test_save_app_missing_tool_is_an_error(client):
    result = await client.call_tool("save_current_app", _save_args(
        f"test-{uuid.uuid4().hex[:8]}",
        tool_names=["no-such-tool"],
    ), raise_on_error=False)
    assert result.is_error


async def test_load_app_missing_is_an_error(client):
    result = await client.call_tool("load_app", {"name": "9999-99-99-no-such-app"}, raise_on_error=False)
    assert result.is_error


async def test_save_app_name_is_date_prefixed(client):
    name = f"test-{uuid.uuid4().hex[:8]}"
    try:
        await client.call_tool("display_ui_to_user", {"html_fragment": "<p>x</p>"})
        await client.call_tool("save_current_app", _save_args(name))

        assert _app_dir(canonical_app_name(name)).is_dir()
    finally:
        shutil.rmtree(_app_dir(canonical_app_name(name)), ignore_errors=True)
