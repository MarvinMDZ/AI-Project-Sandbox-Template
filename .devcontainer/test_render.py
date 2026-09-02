"""Unit tests for render.py. Run: python3 -m unittest discover -s .devcontainer -p "test_*.py" -v"""
from __future__ import annotations

import json
import shutil
import tempfile
import tomllib
import unittest
from pathlib import Path

import render

MODELS = {
    "fast": {"claude": "haiku", "codex": None, "codex_reasoning_effort": "low"},
    "standard": {"claude": "sonnet", "codex": None, "codex_reasoning_effort": "medium"},
    "inherit": {"claude": "inherit", "codex": None},
}
AGENT = """---
name: sample
description: Use for a sample: it keeps the colon.
model: standard
tools: Read, Grep
sandbox: read-only
---

Body line one.
A backslash \\ and a "triple" quote: \"\"\" done.
"""


class ParseFrontmatterTests(unittest.TestCase):
    def test_flat_keys_and_body(self):
        meta, body = render.parse_frontmatter(AGENT, Path("sample.md"))
        self.assertEqual(meta["name"], "sample")
        self.assertEqual(meta["description"], "Use for a sample: it keeps the colon.")
        self.assertEqual(meta["tools"], "Read, Grep")
        self.assertTrue(body.startswith("Body line one."))

    def test_rejects_missing_unterminated_and_nested(self):
        with self.assertRaisesRegex(ValueError, "missing frontmatter"):
            render.parse_frontmatter("name: x\n", Path("a.md"))
        with self.assertRaisesRegex(ValueError, "unterminated frontmatter"):
            render.parse_frontmatter("---\nname: x\n", Path("a.md"))
        with self.assertRaisesRegex(ValueError, "unsupported frontmatter line"):
            render.parse_frontmatter("---\nhooks:\n  - x\n---\nbody\n", Path("a.md"))


class TomlMultilineTests(unittest.TestCase):
    def test_round_trips_backslashes_and_triple_quotes(self):
        body = 'line \\ one\nsay """hi"""\ntrailing\n'
        parsed = tomllib.loads("x = " + render.toml_multiline(body))
        # TOML trims only the newline after the opening delimiter; the one before the closing
        # delimiter stays, so Codex receives the body with exactly one trailing newline.
        self.assertEqual(parsed["x"], body.rstrip("\n") + "\n")


class RenderAgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def agent_file(self, text: str) -> Path:
        path = self.tmp / "sample.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_maps_profile_and_splits_tool_specific_keys(self):
        name, claude_md, codex_toml = render.render_agent(self.agent_file(AGENT), MODELS)
        self.assertEqual(name, "sample")
        self.assertIn('model: "sonnet"', claude_md)
        self.assertIn('tools: "Read, Grep"', claude_md)
        self.assertNotIn("sandbox", claude_md)
        codex = tomllib.loads(codex_toml)
        self.assertEqual(codex["sandbox_mode"], "read-only")
        self.assertEqual(codex["model_reasoning_effort"], "medium")
        self.assertNotIn("model", codex)
        self.assertTrue(codex["developer_instructions"].startswith("Body line one."))

    def test_rejects_unknown_profile(self):
        text = AGENT.replace("model: standard", "model: turbo")
        with self.assertRaisesRegex(ValueError, "models.json"):
            render.render_agent(self.agent_file(text), MODELS)


class RenderEndToEndTests(unittest.TestCase):
    """Runs the real .ai/ of this repository into a temporary home."""

    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.harness = render.HARNESS

    def source_counts(self) -> tuple[int, int]:
        agents = len(list((self.harness / "agents").glob("*.md")))
        skills = sum(
            len([p for p in (self.harness / g).iterdir() if p.is_dir()])
            for g in ("skills", "workflows")
            if (self.harness / g).is_dir()
        )
        return agents, skills

    def test_renders_every_source_and_is_idempotent(self):
        first = render.render(self.home, self.home)
        second = render.render(self.home, self.home)  # wipe-and-rewrite must not fail on a full home
        self.assertEqual(first, second)
        agents, skills = self.source_counts()
        self.assertEqual(first, {"agents": agents, "skills": skills})
        self.assertEqual(
            (self.home / ".claude" / "settings.json").read_text(encoding="utf-8"),
            (self.harness / "claude" / "settings.json").read_text(encoding="utf-8"),
        )
        config = tomllib.loads((self.home / ".codex" / "config.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["projects"][self.home.as_posix()]["trust_level"], "trusted")
        for toml_file in (self.home / ".codex" / "agents").glob("*.toml"):
            parsed = tomllib.loads(toml_file.read_text(encoding="utf-8"))
            self.assertTrue({"name", "description", "developer_instructions"} <= set(parsed))
        self.assertEqual(len(list((self.home / ".claude" / "agents").glob("*.md"))), agents)
        self.assertEqual(len(list((self.home / ".claude" / "skills").iterdir())), skills)
        self.assertEqual(len(list((self.home / ".agents" / "skills").iterdir())), skills)
        for schema in (self.harness / "schemas").glob("*.json"):
            json.loads(schema.read_text(encoding="utf-8"))


class ValidationAndAtomicityTests(unittest.TestCase):
    """Uses a temporary copy of the repository's .ai/ so sources can be broken safely."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.harness = self.tmp / ".ai"
        shutil.copytree(render.HARNESS, self.harness)
        self.home = self.tmp / "home"
        self.original_harness = render.HARNESS
        render.HARNESS = self.harness
        self.addCleanup(setattr, render, "HARNESS", self.original_harness)

    def write_agent(self, filename: str, text: str) -> None:
        (self.harness / "agents" / filename).write_text(text, encoding="utf-8")

    def test_rejects_unknown_frontmatter_key(self):
        self.write_agent("bad.md", AGENT.replace("tools: Read, Grep", "toools: Read"))
        with self.assertRaisesRegex(ValueError, "unknown frontmatter keys"):
            render.render(self.home, self.home)

    def test_rejects_invalid_name(self):
        self.write_agent("bad.md", AGENT.replace("name: sample", "name: ../evil"))
        with self.assertRaisesRegex(ValueError, "must match"):
            render.render(self.home, self.home)

    def test_rejects_duplicate_name(self):
        self.write_agent("one.md", AGENT)
        self.write_agent("two.md", AGENT)
        with self.assertRaisesRegex(ValueError, "duplicate agent name"):
            render.render(self.home, self.home)

    def test_rejects_profile_without_claude_entry(self):
        models = json.loads((self.harness / "models.json").read_text(encoding="utf-8"))
        models["broken"] = {"codex": None}
        (self.harness / "models.json").write_text(json.dumps(models), encoding="utf-8")
        self.write_agent("bad.md", AGENT.replace("model: standard", "model: broken"))
        with self.assertRaisesRegex(ValueError, "needs a `claude` entry"):
            render.render(self.home, self.home)

    def test_failed_render_leaves_previous_output_untouched(self):
        before = render.render(self.home, self.home)
        settings = (self.home / ".claude" / "settings.json").read_text(encoding="utf-8")
        self.write_agent("bad.md", AGENT.replace("tools: Read, Grep", "toools: Read"))
        with self.assertRaises(ValueError):
            render.render(self.home, self.home)
        self.assertEqual((self.home / ".claude" / "settings.json").read_text(encoding="utf-8"), settings)
        self.assertTrue((self.home / ".codex" / "config.toml").is_file())
        self.assertEqual(len(list((self.home / ".claude" / "agents").glob("*.md"))), before["agents"])

    def test_missing_skills_directory_is_not_an_error(self):
        shutil.rmtree(self.harness / "skills")
        counts = render.render(self.home, self.home)
        workflows = len([p for p in (self.harness / "workflows").iterdir() if p.is_dir()])
        self.assertEqual(counts["skills"], workflows)


if __name__ == "__main__":
    unittest.main()
