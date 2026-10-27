import json
import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).parents[3]
_PLUGIN_ROOT_VAR = "${CLAUDE_PLUGIN_ROOT}"


def _load(rel_path: str) -> dict:
    return json.loads((_REPO_ROOT / rel_path).read_text())


def test_plugin_manifest_runs_the_lustereczko_entry_point():
    manifest = _load(".claude-plugin/plugin.json")
    server = manifest["mcpServers"]["lustereczko"]
    args = server["args"]

    project = args[args.index("--project") + 1]
    assert project.startswith(_PLUGIN_ROOT_VAR)
    assert (_REPO_ROOT / project.removeprefix(_PLUGIN_ROOT_VAR).lstrip("/") / "pyproject.toml").exists()

    pyproject = tomllib.loads((_REPO_ROOT / "mcp" / "pyproject.toml").read_text())
    assert args[-1] in pyproject["project"]["scripts"]


def test_marketplace_lists_the_plugin_from_the_repo_root():
    manifest = _load(".claude-plugin/plugin.json")
    marketplace = _load(".claude-plugin/marketplace.json")
    entries = {p["name"]: p for p in marketplace["plugins"]}
    assert entries[manifest["name"]]["source"] == "./"
