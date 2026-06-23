import json
import shutil
import uuid

from main.tools.apps import _APPS_DIR, _CURRENT_UI_FILE, _app_dir_for_name
from main.tools.custom import _TOOLS_DIR


def _cleanup(name: str):
    d = _app_dir_for_name(name)
    if d:
        shutil.rmtree(d)


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
        assert (_app_dir_for_name(name) / "frontend.html").read_text() == sentinel
    finally:
        _cleanup(name)


async def test_save_app_writes_separate_files(client):
    name = f"test-{uuid.uuid4().hex[:8]}"
    catalog = f"catalog-{uuid.uuid4().hex[:8]}"
    context = f"context-{uuid.uuid4().hex[:8]}"
    try:
        await client.call_tool("display_ui_to_user", {"html_fragment": "<p>x</p>"})
        await client.call_tool("save_current_app", _save_args(name, catalog_description=catalog, agent_context=context))
        app_dir = _app_dir_for_name(name)
        assert (app_dir / "catalog_description.txt").read_text() == catalog
        assert (app_dir / "agent_context.md").read_text() == context
        assert (app_dir / "frontend.html").exists()
    finally:
        _cleanup(name)


async def test_save_app_directory_name_includes_date_and_time(client):
    name = f"test-{uuid.uuid4().hex[:8]}"
    try:
        await client.call_tool("display_ui_to_user", {"html_fragment": "<p>x</p>"})
        await client.call_tool("save_current_app", _save_args(name))
        app_dir = _app_dir_for_name(name)
        # Directory name should be YYYY-MM-DD-HHMM-{name}
        import re
        assert re.match(r"^\d{4}-\d{2}-\d{2}-\d{4}-", app_dir.name)
        assert app_dir.name.endswith(f"-{name}")
    finally:
        _cleanup(name)


async def test_save_app_assigns_unique_name_on_conflict(client):
    name = f"test-{uuid.uuid4().hex[:8]}"
    try:
        await client.call_tool("display_ui_to_user", {"html_fragment": "<p>x</p>"})
        r1 = await client.call_tool("save_current_app", _save_args(name))
        r2 = await client.call_tool("save_current_app", _save_args(name))
        assert r1.content[0].text == f"App saved as '{name}'."
        assert r2.content[0].text == f"App saved as '{name}-2'."
        assert _app_dir_for_name(name) is not None
        assert _app_dir_for_name(f"{name}-2") is not None
    finally:
        _cleanup(name)
        _cleanup(f"{name}-2")


async def test_list_saved_apps_empty(client):
    _APPS_DIR.mkdir(parents=True, exist_ok=True)
    stash = _APPS_DIR.parent / f"_apps_stash_{uuid.uuid4().hex[:8]}"
    stash.mkdir()
    try:
        for item in list(_APPS_DIR.iterdir()):
            item.rename(stash / item.name)
        result = await client.call_tool("list_saved_apps")
        assert json.loads(result.content[0].text) == []
    finally:
        for item in stash.iterdir():
            item.rename(_APPS_DIR / item.name)
        stash.rmdir()


async def test_list_saved_apps_separates_name_and_date(client):
    name = f"test-{uuid.uuid4().hex[:8]}"
    catalog = f"catalog-{uuid.uuid4().hex[:8]}"
    try:
        await client.call_tool("display_ui_to_user", {"html_fragment": "<p>x</p>"})
        await client.call_tool("save_current_app", _save_args(name, catalog_description=catalog))
        apps = json.loads((await client.call_tool("list_saved_apps")).content[0].text)
        match = next((a for a in apps if a["name"] == name), None)
        assert match is not None
        assert match["catalog_description"] == catalog
        assert "saved_at" in match
        assert ":" in match["saved_at"]   # formatted as HH:MM
    finally:
        _cleanup(name)


async def test_load_app_takes_bare_name(client):
    name = f"test-{uuid.uuid4().hex[:8]}"
    sentinel_html = f"<p>{uuid.uuid4()}</p>"
    sentinel_context = f"ctx-{uuid.uuid4().hex[:8]}"
    try:
        await client.call_tool("display_ui_to_user", {"html_fragment": sentinel_html})
        await client.call_tool("save_current_app", _save_args(name, agent_context=sentinel_context))
        result = await client.call_tool("load_app", {"name": name})
        payload = json.loads(result.content[0].text)
        assert payload["frontend"] == sentinel_html
        assert payload["agent_context"] == sentinel_context
        assert payload["tools"] == {}
        assert "instructions" in payload
    finally:
        _cleanup(name)


async def test_load_app_missing_is_an_error(client):
    result = await client.call_tool("load_app", {"name": "no-such-app"}, raise_on_error=False)
    assert result.is_error


async def test_save_app_copies_tools_into_app_directory(client):
    app_name = f"test-{uuid.uuid4().hex[:8]}"
    tool_name = f"tool-{uuid.uuid4().hex[:8]}"
    tool_code = f"def run(**kwargs): return {uuid.uuid4()!r}"
    try:
        await client.call_tool("add_custom_tool", {"name": tool_name, "code": tool_code})
        await client.call_tool("display_ui_to_user", {"html_fragment": "<p>x</p>"})
        await client.call_tool("save_current_app", _save_args(app_name, tool_names=[tool_name]))
        saved = (_app_dir_for_name(app_name) / "tools" / f"{tool_name}.py").read_text()
        assert saved == tool_code
    finally:
        _cleanup(app_name)
        (_TOOLS_DIR / f"{tool_name}.py").unlink(missing_ok=True)


async def test_load_app_returns_tools(client):
    app_name = f"test-{uuid.uuid4().hex[:8]}"
    tool_name = f"tool-{uuid.uuid4().hex[:8]}"
    tool_code = f"def run(**kwargs): return {uuid.uuid4()!r}"
    try:
        await client.call_tool("add_custom_tool", {"name": tool_name, "code": tool_code})
        await client.call_tool("display_ui_to_user", {"html_fragment": "<p>x</p>"})
        await client.call_tool("save_current_app", _save_args(app_name, tool_names=[tool_name]))
        result = await client.call_tool("load_app", {"name": app_name})
        assert json.loads(result.content[0].text)["tools"][tool_name] == tool_code
    finally:
        _cleanup(app_name)
        (_TOOLS_DIR / f"{tool_name}.py").unlink(missing_ok=True)


async def test_save_app_missing_tool_is_an_error(client):
    await client.call_tool("display_ui_to_user", {"html_fragment": "<p>x</p>"})
    result = await client.call_tool("save_current_app", _save_args(
        f"test-{uuid.uuid4().hex[:8]}",
        tool_names=["no-such-tool"],
    ), raise_on_error=False)
    assert result.is_error
