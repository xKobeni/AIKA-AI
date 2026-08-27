"""Discover and validate local, instruction-only AIKA skills."""

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re

from config.settings import settings


logger = logging.getLogger(__name__)

SUPPORTED_SKILL_VERSIONS = frozenset({"1.0"})
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_REQUIRED_FIELDS = frozenset({
    "id",
    "name",
    "description",
    "version",
    "required_tools",
})
_OPTIONAL_FIELDS = frozenset({"allowed_agents", "enabled"})


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    name: str
    description: str
    version: str
    instructions: str
    required_tools: tuple[str, ...]
    allowed_agents: tuple[str, ...] | None
    enabled: bool
    directory_name: str


@dataclass(frozen=True)
class SkillIssue:
    source: str
    error: str


class SkillRegistry:
    """Load skills from direct child directories of one configured root."""

    def __init__(
        self,
        root_path=None,
        *,
        max_skills=None,
        max_manifest_bytes=None,
        max_instruction_bytes=None,
    ):
        self.root_path = Path(
            root_path
            if root_path is not None
            else settings.skills_path
        )
        self.max_skills = self._positive_limit(
            max_skills,
            settings.skill_max_count,
        )
        self.max_manifest_bytes = self._positive_limit(
            max_manifest_bytes,
            settings.skill_max_manifest_bytes,
        )
        self.max_instruction_bytes = self._positive_limit(
            max_instruction_bytes,
            settings.skill_max_instruction_bytes,
        )
        self.skills: dict[str, SkillDefinition] = {}
        self.issues: list[SkillIssue] = []
        self.reload()

    @staticmethod
    def _positive_limit(value, default):
        selected = default if value is None else value
        if isinstance(selected, bool) or not isinstance(selected, int):
            return max(1, int(default))
        return max(1, selected)

    @staticmethod
    def _inside(path, root):
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _bounded_text(value, field, *, maximum, allow_empty=False):
        if not isinstance(value, str):
            raise ValueError(f"'{field}' must be a string")
        value = value.strip()
        if not value and not allow_empty:
            raise ValueError(f"'{field}' must not be empty")
        if len(value) > maximum:
            raise ValueError(f"'{field}' exceeds {maximum} characters")
        return value

    @staticmethod
    def _identifier_list(value, field):
        if not isinstance(value, list):
            raise ValueError(f"'{field}' must be a list")
        output = []
        for item in value:
            if not isinstance(item, str) or not _IDENTIFIER.fullmatch(item):
                raise ValueError(f"'{field}' contains an invalid identifier")
            if item in output:
                raise ValueError(f"'{field}' contains a duplicate identifier")
            output.append(item)
        return tuple(output)

    def _read_bounded(self, path, maximum, label):
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise ValueError(f"could not inspect {label}") from exc
        if size > maximum:
            raise ValueError(f"{label} exceeds {maximum} bytes")
        try:
            return path.read_bytes().decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{label} must use UTF-8") from exc
        except OSError as exc:
            raise ValueError(f"could not read {label}") from exc

    def _validate_path(self, path, root, skill_root, label):
        if path.is_symlink():
            raise ValueError(f"{label} must not be a symbolic link")
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise ValueError(f"missing {label}") from exc
        if not self._inside(resolved, root) or not self._inside(
            resolved, skill_root
        ):
            raise ValueError(f"{label} escapes the skill directory")
        if not resolved.is_file():
            raise ValueError(f"missing {label}")
        return resolved

    def _load_directory(self, directory, root):
        source = directory.name
        if directory.is_symlink():
            raise ValueError("skill directory must not be a symbolic link")
        if not _IDENTIFIER.fullmatch(source):
            raise ValueError("skill directory has an invalid identifier")
        try:
            skill_root = directory.resolve(strict=True)
        except OSError as exc:
            raise ValueError("could not resolve skill directory") from exc
        if not self._inside(skill_root, root):
            raise ValueError("skill directory escapes the configured root")

        manifest_path = self._validate_path(
            directory / "skill.json",
            root,
            skill_root,
            "skill.json",
        )
        instructions_path = self._validate_path(
            directory / "SKILL.md",
            root,
            skill_root,
            "SKILL.md",
        )
        manifest_text = self._read_bounded(
            manifest_path,
            self.max_manifest_bytes,
            "skill.json",
        )
        try:
            manifest = json.loads(manifest_text)
        except json.JSONDecodeError as exc:
            raise ValueError("skill.json is not valid JSON") from exc
        if not isinstance(manifest, dict):
            raise ValueError("skill.json must contain an object")

        missing = sorted(_REQUIRED_FIELDS - set(manifest))
        if missing:
            raise ValueError("missing fields: " + ", ".join(missing))
        unknown = sorted(set(manifest) - _REQUIRED_FIELDS - _OPTIONAL_FIELDS)
        if unknown:
            raise ValueError("unknown fields: " + ", ".join(unknown))

        skill_id = self._bounded_text(
            manifest["id"], "id", maximum=64
        )
        if not _IDENTIFIER.fullmatch(skill_id):
            raise ValueError("'id' must be a safe lowercase identifier")
        if skill_id != source:
            raise ValueError("skill id must match its directory name")
        name = self._bounded_text(
            manifest["name"], "name", maximum=100
        )
        description = self._bounded_text(
            manifest["description"], "description", maximum=500
        )
        version = self._bounded_text(
            manifest["version"], "version", maximum=32
        )
        if version not in SUPPORTED_SKILL_VERSIONS:
            raise ValueError(f"unsupported skill version: {version}")
        required_tools = self._identifier_list(
            manifest["required_tools"], "required_tools"
        )
        allowed_agents = None
        if "allowed_agents" in manifest:
            allowed_agents = self._identifier_list(
                manifest["allowed_agents"], "allowed_agents"
            )
        enabled = manifest.get("enabled", True)
        if type(enabled) is not bool:
            raise ValueError("'enabled' must be true or false")

        instructions = self._read_bounded(
            instructions_path,
            self.max_instruction_bytes,
            "SKILL.md",
        ).strip()
        if not instructions:
            raise ValueError("SKILL.md must not be empty")

        return SkillDefinition(
            id=skill_id,
            name=name,
            description=description,
            version=version,
            instructions=instructions,
            required_tools=required_tools,
            allowed_agents=allowed_agents,
            enabled=enabled,
            directory_name=source,
        )

    def reload(self):
        self.skills = {}
        self.issues = []
        try:
            root = self.root_path.resolve(strict=False)
        except OSError:
            self.issues.append(SkillIssue("skills", "could not resolve skill root"))
            return self.skills
        if not root.exists():
            return self.skills
        if root.is_symlink() or not root.is_dir():
            self.issues.append(
                SkillIssue("skills", "configured skill root must be a directory")
            )
            return self.skills

        try:
            directories = sorted(
                (item for item in root.iterdir() if item.is_dir()),
                key=lambda item: item.name,
            )
        except OSError:
            self.issues.append(SkillIssue("skills", "could not list skill root"))
            return self.skills

        if len(directories) > self.max_skills:
            self.issues.append(SkillIssue(
                "skills",
                f"skill count exceeds configured maximum of {self.max_skills}",
            ))
            directories = directories[:self.max_skills]

        for directory in directories:
            source = directory.name
            try:
                skill = self._load_directory(directory, root)
                if skill.id in self.skills:
                    raise ValueError(f"duplicate skill id: {skill.id}")
                self.skills[skill.id] = skill
            except ValueError as exc:
                self.issues.append(SkillIssue(source, str(exc)))
                logger.warning(
                    "Skill rejected | source=%s reason=%s",
                    source,
                    str(exc),
                )
            except Exception as exc:
                self.issues.append(SkillIssue(source, "unexpected validation error"))
                logger.warning(
                    "Skill rejected | source=%s error_type=%s",
                    source,
                    type(exc).__name__,
                )
        return self.skills

    def refresh_from_settings(self):
        self.root_path = Path(settings.skills_path)
        self.max_skills = self._positive_limit(
            settings.skill_max_count,
            100,
        )
        self.max_manifest_bytes = self._positive_limit(
            settings.skill_max_manifest_bytes,
            16384,
        )
        self.max_instruction_bytes = self._positive_limit(
            settings.skill_max_instruction_bytes,
            12000,
        )
        return self.reload()

    def get(self, skill_id):
        return self.skills.get(str(skill_id or "").strip().lower())

    def get_all(self):
        return [self.skills[key] for key in sorted(self.skills)]
