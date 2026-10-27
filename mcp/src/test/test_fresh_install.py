"""A fresh install (extension bundle, new clone) has no server-scratchpad/ yet."""
import main.tools.apps as apps
import main.tools.custom as custom


async def test_display_ui_creates_missing_scratchpad(client, tmp_path, monkeypatch):
    monkeypatch.setattr(apps, "_CURRENT_UI_FILE", tmp_path / "server-scratchpad" / "current_ui.html")
    await client.call_tool("display_ui_to_user", {"html_fragment": "<p>hi</p>"})
    assert apps._CURRENT_UI_FILE.read_text() == "<p>hi</p>"


async def test_add_custom_tool_creates_missing_scratchpad(client, tmp_path, monkeypatch):
    monkeypatch.setattr(custom, "_TOOLS_DIR", tmp_path / "server-scratchpad" / "tools")
    await client.call_tool("add_custom_tool", {"name": "adder", "code": "def run(a, b): return a + b"})
    assert (custom._TOOLS_DIR / "adder.py").exists()
