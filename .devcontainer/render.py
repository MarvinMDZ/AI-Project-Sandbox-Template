#!/usr/bin/env python3
"""Render ./.ai into the Claude Code and Codex user-level config directories.

.ai/ is the single source of truth. build() turns it into a manifest: every target this script
owns under $HOME with its expected content. install() wipes the managed targets and writes the
manifest; verify() compares a real home against it and reports drift. Session state (credentials,
sessions, history, plugin caches) is never touched.

    .ai/RULES.md             -> baked into the image by the Dockerfile (/etc/claude-code/CLAUDE.md,
                                /etc/codex/AGENTS.md); here only ~/.codex/AGENTS.md -> /etc/codex/AGENTS.md
    .ai/claude/settings.json -> ~/.claude/settings.json
    .ai/codex/config.toml    -> ~/.codex/config.toml (+ trust entry for the workspace)
    .ai/agents/*.md          -> ~/.claude/agents/*.md, ~/.codex/agents/*.toml
    .ai/skills/*/            -> ~/.claude/skills/*, ~/.agents/skills/*
    .ai/workflows/*/         -> ~/.claude/skills/*, ~/.agents/skills/*

Usage:
    render.py [--home DIR] [--workspace DIR]   render for real
    render.py --check [--workspace DIR]        render into a temp dir, verify it, list the files (CI)
    render.py --verify [--home DIR] [--workspace DIR]
                                              compare a rendered home with .ai/: exit 0 verified,
                                              1 broken (missing or forbidden), 2 drift (differs or extra)
"""
from __future__ import annotations

import argparse
import filecmp
import json
import re
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import NamedTuple

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
# Managed names the manifest never produces. Present after a render means someone wrote them by
# hand; both shadow or duplicate the image rules, so verify() reports them as broken, not as drift.
FORBIDDEN = (Path(".claude/CLAUDE.md"), Path(".codex/AGENTS.override.md"))


class Symlink(NamedTuple):
    target: Path


class Finding(NamedTuple):
    status: str  # missing | forbidden | differs | extra | skipped
    path: str
    detail: str = ""


Manifest = dict[Path, str | Path | Symlink]


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


def build(workspace: Path) -> Manifest:
    """Read and validate every source under .ai/ and return the manifest: {target relative to $HOME:
    file text, directory to copy, or Symlink}. Touches nothing on disk, so a broken source cannot
    leave a half-rendered home."""
    models = {k: v for k, v in json.loads((HARNESS / "models.json").read_text(encoding="utf-8")).items()
              if not k.startswith("_")}
    if not (HARNESS / "RULES.md").is_file():
        raise FileNotFoundError(f"{HARNESS / 'RULES.md'}: missing; the image build copies it")
    out: Manifest = {}

    settings = (HARNESS / "claude" / "settings.json").read_text(encoding="utf-8")
    json.loads(settings)
    out[Path(".claude/settings.json")] = settings

    config = (HARNESS / "codex" / "config.toml").read_text(encoding="utf-8")
    config += f'\n[projects.{json.dumps(workspace.as_posix())}]\ntrust_level = "trusted"\n'
    tomllib.loads(config)
    out[Path(".codex/config.toml")] = config
    # Codex only reads $CODEX_HOME/AGENTS.md; the image rules live in /etc, so link them.
    out[Path(".codex/AGENTS.md")] = Symlink(CODEX_IMAGE_RULES)

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


def install(home: Path, manifest: Manifest) -> None:
    """Wipe the managed targets and write the manifest. Call only after build() succeeded."""
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
    for rel, content in manifest.items():
        target = home / rel
        if isinstance(content, Symlink):
            # Only where the image rules exist: elsewhere (CI runner, a Windows host running --check)
            # the link would dangle, and verify() reports the entry as skipped instead of missing.
            if content.target.is_file():
                target.symlink_to(content.target)
        elif isinstance(content, Path):
            shutil.copytree(content, target)
        else:
            target.write_text(content, encoding="utf-8")


def dir_differs(src: Path, dst: Path) -> bool:
    """True unless dst holds exactly the files of src with identical bytes."""
    src_files = {p.relative_to(src) for p in src.rglob("*") if p.is_file()}
    dst_files = {p.relative_to(dst) for p in dst.rglob("*") if p.is_file()}
    if src_files != dst_files:
        return True
    return any(not filecmp.cmp(src / p, dst / p, shallow=False) for p in src_files)


def verify(home: Path, manifest: Manifest) -> list[Finding]:
    """Compare a rendered home with the manifest without modifying anything. Reports entries that are
    missing, forbidden (hand-written rules files), different, or extra inside the managed targets."""
    findings: list[Finding] = []
    for rel, content in manifest.items():
        target = home / rel
        if isinstance(content, Symlink):
            if not content.target.is_file():
                detail = f"target {content.target.as_posix()} absent on this host"
                findings.append(Finding("skipped", rel.as_posix(), detail))
            elif not target.is_symlink() or target.readlink() != content.target:
                findings.append(Finding("missing", rel.as_posix(), f"symlink to {content.target}"))
        elif isinstance(content, Path):
            if not target.is_dir():
                findings.append(Finding("missing", rel.as_posix()))
            elif dir_differs(content, target):
                findings.append(Finding("differs", rel.as_posix()))
        elif not target.is_file():
            findings.append(Finding("missing", rel.as_posix()))
        elif target.read_text(encoding="utf-8") != content:
            findings.append(Finding("differs", rel.as_posix()))
    for rel in FORBIDDEN:
        if (home / rel).exists():
            findings.append(Finding("forbidden", rel.as_posix(), "hand-written rules file; shadows the image rules"))
    known = set(manifest) | set(FORBIDDEN)
    managed = [home / ".claude" / n for n in CLAUDE_MANAGED] + [home / ".codex" / n for n in CODEX_MANAGED]
    managed.append(home / ".agents" / "skills")
    for path in managed:
        children = list(path.iterdir()) if path.is_dir() and not path.is_symlink() else [path]
        for child in children:
            rel = child.relative_to(home)
            if rel not in known and (child.exists() or child.is_symlink()):
                findings.append(Finding("extra", rel.as_posix(), "not produced by .ai/; the next start removes it"))
    return findings


def exit_code(findings: list[Finding]) -> int:
    """0 verified; 1 broken (missing or forbidden: the render did not complete or was overridden);
    2 drift (differs or extra: a session or a hand edit changed it; restart or render to reset)."""
    statuses = {f.status for f in findings}
    if statuses & {"missing", "forbidden"}:
        return 1
    if statuses & {"differs", "extra"}:
        return 2
    return 0


def counts(manifest: Manifest) -> dict[str, int]:
    return {
        "agents": sum(1 for p in manifest if p.parts[:2] == (".claude", "agents")),
        "skills": sum(1 for p in manifest if p.parts[:2] == (".claude", "skills")),
    }


def describe(manifest: Manifest) -> str:
    c = counts(manifest)
    return f"{c['agents']} agents, {c['skills']} skills/workflows"


def render(home: Path, workspace: Path) -> dict[str, int]:
    manifest = build(workspace)
    install(home, manifest)
    return counts(manifest)


def print_findings(findings: list[Finding]) -> None:
    for f in findings:
        print(f"{f.status:<9} {f.path}" + (f"  ({f.detail})" if f.detail else ""))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true", help="render into a temp dir, verify it, list the files")
    parser.add_argument("--verify", action="store_true", help="compare --home with .ai/ (exit 0, 1 broken, 2 drift)")
    args = parser.parse_args()
    workspace = args.workspace.resolve()

    if args.check:
        manifest = build(workspace)
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            install(home, manifest)
            findings = verify(home, manifest)
            for path in sorted(p for p in home.rglob("*") if p.is_file() or p.is_symlink()):
                print(path.relative_to(home).as_posix())
        print_findings(findings)
        if exit_code(findings) != 0:
            print("render.py: --check failed: install() and verify() disagree", file=sys.stderr)
            return 1
        print(f"harness OK: {describe(manifest)}")
        return 0

    if args.verify:
        manifest = build(workspace)
        findings = verify(args.home, manifest)
        print_findings(findings)
        rc = exit_code(findings)
        print(f"harness {('verified', 'broken', 'drift')[rc]}: {describe(manifest)} in {args.home}")
        return rc

    manifest = build(workspace)
    install(args.home, manifest)
    print(f"harness rendered from {HARNESS}: {describe(manifest)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, FileNotFoundError, tomllib.TOMLDecodeError, json.JSONDecodeError) as exc:
        print(f"render.py: {exc}", file=sys.stderr)
        sys.exit(1)
