#!/usr/bin/env python3
"""Render ./.ai into the Claude Code and Codex user-level config directories.

.ai/ is the single source of truth. Everything this script manages is deleted and
rewritten on every container start, so a removed agent, skill or rule leaves no trace.
Session state (credentials, sessions, history, plugin caches) is never touched.

    .ai/RULES.md             -> baked into the image by the Dockerfile (/etc/claude-code/CLAUDE.md,
                                /etc/codex/AGENTS.md); here only ~/.codex/AGENTS.md -> /etc/codex/AGENTS.md
    .ai/claude/settings.json -> ~/.claude/settings.json
    .ai/codex/config.toml    -> ~/.codex/config.toml (+ trust entry for the workspace)
    .ai/agents/*.md          -> ~/.claude/agents/*.md, ~/.codex/agents/*.toml
    .ai/skills/*/            -> ~/.claude/skills/*, ~/.agents/skills/*
    .ai/workflows/*/         -> ~/.claude/skills/*, ~/.agents/skills/*

Usage:
    render.py [--home DIR] [--workspace DIR]   render for real
    render.py --check                         render into a temp dir and validate (CI)
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent / ".ai"
# Codex has no managed rules path; the image ships RULES.md here and $CODEX_HOME/AGENTS.md links to it.
CODEX_IMAGE_RULES = Path("/etc/codex/AGENTS.md")

# Frontmatter keys Claude Code documents for a subagent file (flat values only; nested keys such
# as hooks, mcpServers and experimental cannot be expressed in this parser). Everything else is
# rejected, so a typo cannot silently drop a restriction.
CLAUDE_AGENT_KEYS = {
    "name", "description", "tools", "disallowedTools", "model", "permissionMode",
    "skills", "maxTurns", "memory", "effort", "background", "isolation", "color", "initialPrompt",
}
HARNESS_ONLY_KEYS = {"sandbox"}  # consumed by the Codex side only
# Valid for both CLIs, and a safe file name: the value becomes ~/.claude/agents/<name>.md.
AGENT_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")
# ponytail: managed = wiped and rewritten. Not wiped: ~/.claude/plugins (enablement lives in
# settings.json) and ~/.codex/skills (Codex keeps its bundled .system skills there).
CLAUDE_MANAGED = ["skills", "agents", "commands", "CLAUDE.md", "settings.json"]
# AGENTS.override.md is wiped too: Codex would read it INSTEAD of the linked image rules.
CODEX_MANAGED = ["agents", "prompts", "AGENTS.md", "AGENTS.override.md", "config.toml"]


def parse_frontmatter(text: str, src: Path) -> tuple[dict[str, str], str]:
    """Flat `key: value` frontmatter only (one line per key). Enough for agents; keeps stdlib-only."""
    if not text.startswith("---\n"):
        raise ValueError(f"{src}: missing frontmatter")
    head, sep, body = text[4:].partition("\n---\n")
    if not sep:
        raise ValueError(f"{src}: unterminated frontmatter")
    meta: dict[str, str] = {}
    for line in head.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, colon, value = line.partition(":")
        if not colon or line[0].isspace():
            raise ValueError(f"{src}: unsupported frontmatter line {line!r} (flat key: value only)")
        meta[key.strip()] = value.strip().strip("\"'")
    return meta, body.lstrip("\n")


def toml_multiline(s: str) -> str:
    s = s.replace("\\", "\\\\").replace('"""', '""\\"')
    return '"""\n' + s.rstrip("\n") + '\n"""'


def render_agent(src: Path, models: dict) -> tuple[str, str, str]:
    meta, body = parse_frontmatter(src.read_text(encoding="utf-8"), src)
    for key in ("name", "description"):
        if not meta.get(key):
            raise ValueError(f"{src}: frontmatter needs `{key}`")
    if len(meta["description"]) > 1024:
        raise ValueError(f"{src}: description must be one line (<=1024 chars)")
    if not AGENT_NAME.fullmatch(meta["name"]):
        raise ValueError(f"{src}: agent name {meta['name']!r} must match {AGENT_NAME.pattern}")
    unknown = sorted(set(meta) - CLAUDE_AGENT_KEYS - HARNESS_ONLY_KEYS)
    if unknown:
        allowed = sorted(CLAUDE_AGENT_KEYS | HARNESS_ONLY_KEYS)
        raise ValueError(f"{src}: unknown frontmatter keys {unknown}; allowed: {allowed}")
    profile_name = meta.get("model", "inherit")
    if profile_name not in models:
        raise ValueError(f"{src}: model profile {profile_name!r} not in .ai/models.json")
    profile = models[profile_name]
    if "claude" not in profile:
        raise ValueError(f".ai/models.json: profile {profile_name!r} needs a `claude` entry")

    claude = {k: v for k, v in meta.items() if k in CLAUDE_AGENT_KEYS}
    claude["model"] = profile["claude"]
    claude_md = "---\n" + "".join(f"{k}: {json.dumps(v)}\n" for k, v in claude.items()) + "---\n\n" + body

    lines = [f"name = {json.dumps(meta['name'])}", f"description = {json.dumps(meta['description'])}"]
    if profile.get("codex"):
        lines.append(f"model = {json.dumps(profile['codex'])}")
    if profile.get("codex_reasoning_effort"):
        lines.append(f"model_reasoning_effort = {json.dumps(profile['codex_reasoning_effort'])}")
    if meta.get("sandbox"):
        lines.append(f"sandbox_mode = {json.dumps(meta['sandbox'])}")
    lines.append("developer_instructions = " + toml_multiline(body))
    codex_toml = "\n".join(lines) + "\n"
    tomllib.loads(codex_toml)  # fail loudly here, not inside Codex
    return meta["name"], claude_md, codex_toml


def build(workspace: Path) -> dict[Path, str | Path]:
    """Read and validate every source under .ai/. Returns {target relative to $HOME: file text, or a
    directory to copy}. Touches nothing on disk, so a broken source cannot leave a half-rendered home."""
    models = {k: v for k, v in json.loads((HARNESS / "models.json").read_text(encoding="utf-8")).items()
              if not k.startswith("_")}
    if not (HARNESS / "RULES.md").is_file():
        raise FileNotFoundError(f"{HARNESS / 'RULES.md'}: missing; the image build copies it")
    out: dict[Path, str | Path] = {}

    settings = (HARNESS / "claude" / "settings.json").read_text(encoding="utf-8")
    json.loads(settings)
    out[Path(".claude/settings.json")] = settings

    config = (HARNESS / "codex" / "config.toml").read_text(encoding="utf-8")
    config += f'\n[projects.{json.dumps(workspace.as_posix())}]\ntrust_level = "trusted"\n'
    tomllib.loads(config)
    out[Path(".codex/config.toml")] = config

    for group in ("skills", "workflows"):
        group_dir = HARNESS / group
        if not group_dir.is_dir():  # git drops an emptied directory; that is not an error
            continue
        for skill in sorted(p for p in group_dir.iterdir() if p.is_dir()):
            if not (skill / "SKILL.md").is_file():
                raise ValueError(f"{skill}: missing SKILL.md")
            target = Path(".claude/skills") / skill.name
            if target in out:
                raise ValueError(f"duplicate skill name {skill.name!r} across skills/ and workflows/")
            out[target] = skill
            out[Path(".agents/skills") / skill.name] = skill

    for src in sorted((HARNESS / "agents").glob("*.md")):
        name, claude_md, codex_toml = render_agent(src, models)
        target = Path(".claude/agents") / f"{name}.md"
        if target in out:
            raise ValueError(f"{src}: duplicate agent name {name!r}")
        out[target] = claude_md
        out[Path(".codex/agents") / f"{name}.toml"] = codex_toml

    for schema in (HARNESS / "schemas").glob("*.json"):
        json.loads(schema.read_text(encoding="utf-8"))
    return out


def install(home: Path, outputs: dict[Path, str | Path]) -> None:
    """Wipe the managed targets and write the validated outputs. Call only after build() succeeded."""
    claude, codex, agents_skills = home / ".claude", home / ".codex", home / ".agents" / "skills"
    for base, names in ((claude, CLAUDE_MANAGED), (codex, CODEX_MANAGED)):
        base.mkdir(parents=True, exist_ok=True)
        for name in names:
            target = base / name
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink(missing_ok=True)
    shutil.rmtree(agents_skills, ignore_errors=True)
    for d in (claude / "skills", claude / "agents", codex / "agents", agents_skills):
        d.mkdir(parents=True)
    # Global rules are baked into the image: Claude Code loads /etc/claude-code/CLAUDE.md natively
    # (a stale ~/.claude/CLAUDE.md was wiped above); Codex only reads $CODEX_HOME/AGENTS.md, so link it.
    if CODEX_IMAGE_RULES.is_file():
        (codex / "AGENTS.md").symlink_to(CODEX_IMAGE_RULES)
    for rel, content in outputs.items():
        target = home / rel
        if isinstance(content, Path):
            shutil.copytree(content, target)
        else:
            target.write_text(content, encoding="utf-8")


def render(home: Path, workspace: Path) -> dict[str, int]:
    outputs = build(workspace)
    install(home, outputs)
    return {
        "agents": sum(1 for p in outputs if p.parts[:2] == (".claude", "agents")),
        "skills": sum(1 for p in outputs if p.parts[:2] == (".claude", "skills")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true", help="render into a temp dir and validate")
    args = parser.parse_args()

    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            counts = render(Path(tmp), args.workspace.resolve())
            for path in sorted(p for p in Path(tmp).rglob("*") if p.is_file()):
                print(path.relative_to(tmp).as_posix())
        print(f"harness OK: {counts['agents']} agents, {counts['skills']} skills/workflows")
        return 0

    counts = render(args.home, args.workspace.resolve())
    print(f"harness rendered from {HARNESS}: {counts['agents']} agents, {counts['skills']} skills/workflows")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, FileNotFoundError, tomllib.TOMLDecodeError, json.JSONDecodeError) as exc:
        print(f"render.py: {exc}", file=sys.stderr)
        sys.exit(1)
