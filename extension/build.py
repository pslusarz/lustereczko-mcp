"""Build dist/lustereczko.mcpb, a Claude Desktop extension bundle.

The bundle mirrors the repo layout (manifest.json at the root, then mcp/ and
skills/), so the server's paths relative to the repo root keep working.

    uv run --project mcp python extension/build.py
"""
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_INCLUDE = ["LICENSE", "mcp/pyproject.toml", "mcp/uv.lock", "mcp/src/main", "skills"]
_EXCLUDE_PARTS = {"__pycache__", ".DS_Store"}


def _files(rel: str):
    path = REPO_ROOT / rel
    candidates = sorted(path.rglob("*")) if path.is_dir() else [path]
    for f in candidates:
        if f.is_file() and not _EXCLUDE_PARTS & set(f.relative_to(REPO_ROOT).parts):
            yield f


def build(out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(REPO_ROOT / "extension" / "manifest.json", "manifest.json")
        for rel in _INCLUDE:
            for f in _files(rel):
                zf.write(f, f.relative_to(REPO_ROOT).as_posix())
    return out_path


if __name__ == "__main__":
    out = build(Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "dist" / "lustereczko.mcpb")
    print(f"Built {out}")
