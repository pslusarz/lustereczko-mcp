import re
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent

_SKILLS_DIR = Path(__file__).parents[4] / "skills"


class AgentSkill(BaseModel):
    skill_name: str
    description: str


class AgentSkillList(BaseModel):
    skills: list[AgentSkill]


def _parse_frontmatter_description(path: Path) -> str:
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return ""
    for line in m.group(1).splitlines():
        if line.startswith("description:"):
            return line[len("description:"):].strip()
    return ""


def _skill_name(path: Path) -> str:
    rel = path.relative_to(_SKILLS_DIR)
    return "/".join(rel.parts[:-1]) + ":" + path.stem if len(rel.parts) > 1 else path.stem


def _skill_path(skill_name: str) -> Path:
    if ":" in skill_name:
        dir_part, name = skill_name.rsplit(":", 1)
        return _SKILLS_DIR / dir_part / f"{name}.md"
    return _SKILLS_DIR / f"{skill_name}.md"


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_agent_skills() -> ToolResult:
        """List available agent skills with descriptions. Use get_agent_skill to read one."""
        if not _SKILLS_DIR.exists():
            return ToolResult(content=[TextContent(type="text", text=AgentSkillList(skills=[]).model_dump_json(indent=2))])
        skills = [
            AgentSkill(skill_name=_skill_name(p), description=_parse_frontmatter_description(p))
            for p in sorted(_SKILLS_DIR.rglob("*.md")) if p.stem != "SKILL"
        ]
        return ToolResult(content=[TextContent(type="text", text=AgentSkillList(skills=skills).model_dump_json(indent=2))])

    @mcp.tool()
    def get_agent_skill(
        skill_name: Annotated[str, Field(description="skill_name from list_agent_skills, e.g. recipes:ui-debug")],
    ) -> ToolResult:
        """Read an agent skill document by skill_name."""
        path = _skill_path(skill_name)
        if not path.exists():
            return ToolResult(content=[TextContent(type="text", text=f"Skill '{skill_name}' not found.")])
        return ToolResult(content=[TextContent(type="text", text=path.read_text())])
