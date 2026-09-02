#!/usr/bin/env python3
"""Render ./harness into the Claude Code and Codex user-level config directories.

harness/ is the single source of truth. Everything this script manages is deleted and
rewritten on every container start, so a removed agent, skill or rule leaves no trace.
Session state (credentials, sessions, history, plugin caches) is never touched.

    harness/RULES.md             -> ~/.claude/CLAUDE.md, ~/.codex/AGENTS.md
    harness/claude/settings.json -> ~/.claude/settings.json
    harness/codex/config.toml    -> ~/.codex/config.toml (+ trust entry for the workspace)
    harness/agents/*.md          -> ~/.claude/agents/*.md, ~/.codex/agents/*.toml
    harness/skills/*/            -> ~/.claude/skills/*, ~/.agents/skills/*
    harness/workflows/*/         -> ~/.claude/skills/*, ~/.agents/skills/*

Usage:
    render.py [--home DIR] [--workspace DIR]   render for real
    render.py --check                         render into a temp dir and validate (CI)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent / "harness"

# Frontmatter keys Claude Code understands in a subagent file. Anything else is harness-only.
CLAUDE_AGENT_KEYS = {
    "name", "description", "tools", "disallowedTools", "model", "permissionMode",
    "skills", "maxTurns", "memory", "effort", "background", "isolation",
}
# ponytail: managed = wiped and rewritten. Not wiped: ~/.claude/plugins (enablement lives in
# settings.json) and ~/.codex/skills (Codex keeps its bundled .system skills there).
CLAUDE_MANAGED = ["skills", "agents", "commands", "CLAUDE.md", "settings.json"]
CODEX_MANAGED = ["agents", "prompts", "AGENTS.md", "config.toml"]


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
    profile_name = meta.get("model", "inherit")
    if profile_name not in models:
        raise ValueError(f"{src}: model profile {profile_name!r} not in harness/models.json")
    profile = models[profile_name]

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


def render(home: Path, workspace: Path) -> dict[str, int]:
    models = {k: v for k, v in json.loads((HARNESS / "models.json").read_text(encoding="utf-8")).items()
              if not k.startswith("_")}
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

    rules = (HARNESS / "RULES.md").read_text(encoding="utf-8")
    (claude / "CLAUDE.md").write_text(rules, encoding="utf-8")
    (codex / "AGENTS.md").write_text(rules, encoding="utf-8")

    settings = (HARNESS / "claude" / "settings.json").read_text(encoding="utf-8")
    json.loads(settings)
    (claude / "settings.json").write_text(settings, encoding="utf-8")

    config = (HARNESS / "codex" / "config.toml").read_text(encoding="utf-8")
    config += f'\n[projects.{json.dumps(workspace.as_posix())}]\ntrust_level = "trusted"\n'
    tomllib.loads(config)
    (codex / "config.toml").write_text(config, encoding="utf-8")

    counts = {"agents": 0, "skills": 0}
    for group in ("skills", "workflows"):
        for skill in sorted(p for p in (HARNESS / group).iterdir() if p.is_dir()):
            if not (skill / "SKILL.md").is_file():
                raise ValueError(f"{skill}: missing SKILL.md")
            for dest in (claude / "skills" / skill.name, agents_skills / skill.name):
                if dest.exists():
                    raise ValueError(f"duplicate skill name {skill.name!r} across skills/ and workflows/")
                shutil.copytree(skill, dest)
            counts["skills"] += 1

    for src in sorted((HARNESS / "agents").glob("*.md")):
        name, claude_md, codex_toml = render_agent(src, models)
        (claude / "agents" / f"{name}.md").write_text(claude_md, encoding="utf-8")
        (codex / "agents" / f"{name}.toml").write_text(codex_toml, encoding="utf-8")
        counts["agents"] += 1

    for schema in (HARNESS / "schemas").glob("*.json"):
        json.loads(schema.read_text(encoding="utf-8"))
    return counts


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
