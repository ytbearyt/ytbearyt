"""Discovery and registration of Agent Skills metadata."""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml


logger = logging.getLogger(__name__)
MAX_SKILL_FILE_BYTES = 2 * 1024 * 1024
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str
    path: Path


def create_skill(name: str, skill_context: str, project_root: Path | None = None) -> str:
    """Create a new project Skill without overwriting existing content."""
    skill_name = name.strip() if isinstance(name, str) else ""
    if not SKILL_NAME_PATTERN.fullmatch(skill_name):
        return "错误：Skill 名称必须只包含小写字母、数字和连字符，且不能以连字符开头或结尾"
    if not isinstance(skill_context, str) or not skill_context.strip():
        return "错误：skillContext 不能为空"

    try:
        metadata = _read_skill_metadata_from_text(skill_context)
    except (ValueError, yaml.YAMLError) as exc:
        return f"错误：skillContext 不是有效的 Skill 文件：{exc}"
    if metadata.name != skill_name:
        return f"错误：YAML Frontmatter 中的 name 必须与参数 name 一致：{skill_name}"

    root = project_root or Path.cwd()
    skills_root = root / ".agents" / "skills"
    target_dir = skills_root / skill_name
    if target_dir.exists():
        return f"错误：目标 Skill 已存在，未覆盖原有内容：{target_dir}"
    if skill_name in discover_skills(root):
        return f"错误：已存在同名 Skill，未创建：{skill_name}"

    try:
        target_dir.mkdir(parents=True)
        (target_dir / "SKILL.md").write_text(skill_context, encoding="utf-8")
    except OSError as exc:
        return f"错误：创建 Skill 失败：{exc}"
    return f"已创建 Skill：{skill_name}（{target_dir / 'SKILL.md'}）"


def load_skill(name: str, filename: str = "", skills: Mapping[str, SkillMetadata] | None = None) -> str:
    """Load a Skill's instructions or an additional file inside its directory."""
    registered_skills = discover_skills() if skills is None else skills
    skill = registered_skills.get(name)
    if skill is None:
        return f"错误：未找到 Skill：{name}"

    skill_dir = skill.path.parent.resolve()
    target_name = filename.strip()
    if not target_name:
        candidate = skill.path
    else:
        candidates = _exact_skill_file_candidates(skill_dir, target_name)
        outside_candidate = False
        candidate = None
        for path in candidates:
            resolved_path = path.resolve()
            if not _is_file_inside(resolved_path, skill_dir):
                outside_candidate = outside_candidate or path.exists()
                continue
            if resolved_path.is_file():
                candidate = resolved_path
                break
        if candidate is None and _is_filename_only(target_name):
            matches = sorted(
                path.resolve()
                for path in skill_dir.rglob(target_name)
                if path.is_file() and _is_file_inside(path, skill_dir)
            )
            if len(matches) > 1:
                return "找到多个匹配文件，请提供更具体的 filename：\n" + "\n".join(
                    f"- {_display_path(path, skill_dir)}" for path in matches
                )
            if matches:
                candidate = matches[0]
        if candidate is None and outside_candidate:
            return f"错误：文件路径必须位于 Skill 目录内：{filename}"
    if candidate is None:
        return f"错误：Skill {name} 中未找到文件：{filename}"

    candidate = candidate.resolve()
    if not _is_file_inside(candidate, skill_dir):
        return f"错误：文件路径必须位于 Skill 目录内：{filename}"
    if not candidate.is_file():
        return f"错误：不是文件：{filename}"
    try:
        if candidate.stat().st_size > MAX_SKILL_FILE_BYTES:
            return f"错误：文件过大，限制为 {MAX_SKILL_FILE_BYTES} 字节：{filename or 'SKILL.md'}"
        return candidate.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return f"错误：无法读取 Skill 文件 {filename or 'SKILL.md'}：{exc}"


def _exact_skill_file_candidates(skill_dir: Path, filename: str) -> list[Path]:
    requested = Path(filename)
    if requested.is_absolute():
        return [requested]
    project_root = skill_dir.parents[2]
    return [skill_dir / requested, project_root / requested]


def _is_filename_only(filename: str) -> bool:
    requested = Path(filename)
    return len(requested.parts) == 1 and requested.name == filename


def _is_file_inside(path: Path, skill_dir: Path) -> bool:
    try:
        path.resolve().relative_to(skill_dir)
    except ValueError:
        return False
    return True


def _display_path(path: Path, skill_dir: Path) -> str:
    try:
        return str(path.relative_to(skill_dir))
    except ValueError:
        return str(path)


def discover_skills(project_root: Path | None = None) -> Mapping[str, SkillMetadata]:
    """Discover skill metadata below ``.agents/skills`` without reading bodies."""
    skills_root = (project_root or Path.cwd()) / ".agents" / "skills"
    if not skills_root.is_dir():
        return MappingProxyType({})

    discovered: dict[str, SkillMetadata] = {}
    for skill_dir in sorted(skills_root.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            continue
        try:
            metadata = _read_skill_metadata(skill_file)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            logger.warning("跳过无效 Skill %s：%s", skill_file, exc)
            continue
        if metadata.name in discovered:
            logger.warning("跳过重复 Skill name %r：%s", metadata.name, skill_file)
            continue
        discovered[metadata.name] = metadata
    return MappingProxyType(discovered)


def _read_skill_metadata(skill_file: Path) -> SkillMetadata:
    return _read_skill_metadata_from_text(skill_file.read_text(encoding="utf-8"), skill_file)


def _read_skill_metadata_from_text(content: str, skill_file: Path | None = None) -> SkillMetadata:
    frontmatter = _read_frontmatter_from_text(content)
    values = yaml.safe_load(frontmatter)
    if not isinstance(values, dict):
        raise ValueError("YAML Frontmatter 必须是对象")

    name = values.get("name")
    description = values.get("description")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("缺少必需字段 name")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("缺少必需字段 description")
    return SkillMetadata(name=name.strip(), description=description.strip(), path=skill_file or Path("SKILL.md"))


def _read_frontmatter(skill_file: Path) -> str:
    return _read_frontmatter_from_text(skill_file.read_text(encoding="utf-8"))


def _read_frontmatter_from_text(content: str) -> str:
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("文件必须以 YAML Frontmatter 开始")
    frontmatter: list[str] = []
    for line in lines[1:]:
        if line.strip() in {"---", "..."}:
            return "".join(frontmatter)
        frontmatter.append(line)
    raise ValueError("YAML Frontmatter 未闭合")