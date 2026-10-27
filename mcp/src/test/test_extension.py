import importlib.util
import json
import tomllib
import zipfile
from pathlib import Path

_REPO_ROOT = Path(__file__).parents[3]


def _load_build():
    spec = importlib.util.spec_from_file_location("ext_build", _REPO_ROOT / "extension" / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_matches_the_python_project():
    manifest = json.loads((_REPO_ROOT / "extension" / "manifest.json").read_text())
    pyproject = tomllib.loads((_REPO_ROOT / "mcp" / "pyproject.toml").read_text())
    assert manifest["version"] == pyproject["project"]["version"]
    assert manifest["server"]["mcp_config"]["args"][-1] in pyproject["project"]["scripts"]


def test_bundle_mirrors_repo_layout(tmp_path):
    bundle = _load_build().build(tmp_path / "lustereczko.mcpb")
    names = set(zipfile.ZipFile(bundle).namelist())

    manifest = json.loads(zipfile.ZipFile(bundle).read("manifest.json"))
    assert manifest["server"]["entry_point"] in names
    assert {"mcp/pyproject.toml", "mcp/uv.lock", "skills/SKILL.md", "skills/recipes/margin-comments.md"} <= names
    assert not [n for n in names if "__pycache__" in n or n.startswith(("mcp/src/test", "mcp/.venv"))]
