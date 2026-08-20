#!/usr/bin/env python3
"""Persona extraction and preset rendering for the DSH MVP install.

Single source of truth for the rule "the preset persona is the body of
plugins/agent-plugins/<id>/agents/<id>.md with its YAML frontmatter stripped".
Both dsh/install-mvp.sh (via the `render` subcommand) and the Seam 2 test
(dsh/tests/test_install_mvp.py, via imports) use this module, so the expected
persona can never drift from what actually gets installed.

Rendering contract (mirrors the shipped `standard` preset style):
  - the template keeps a `text: |` literal block whose only content line is
    the __PERSONA_TEXT__ placeholder;
  - render_preset replaces that whole line with the persona lines indented to
    the placeholder's indentation;
  - blank persona lines become truly empty lines (YAML literal blocks treat
    them as empty lines regardless of indentation);
  - a single leading blank line after the closing `---` is dropped: it is
    formatting, not content, and a whitespace-only first content line breaks
    both PyYAML and js-yaml indentation detection.

The persona body keeps its exact remaining bytes, including the trailing
newline; the `|` clip chomping keeps exactly that one trailing line break.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

FRONTMATTER_DELIM = "---"
PLACEHOLDER = "__PERSONA_TEXT__"


def persona_body(agent_md_text: str) -> str:
    """Return the agent markdown body after the first frontmatter pair.

    The body is the exact text following the second `---` delimiter line,
    minus one leading blank line (the separator between frontmatter and body).
    A missing second delimiter raises ValueError.
    """
    lines = agent_md_text.splitlines(keepends=True)
    delimiters = 0
    for i, line in enumerate(lines):
        if line.rstrip("\r\n") == FRONTMATTER_DELIM:
            delimiters += 1
            if delimiters == 2:
                body = "".join(lines[i + 1 :])
                if body.startswith("\n"):
                    body = body[1:]
                return body
    raise ValueError(
        f"agent markdown must contain two '{FRONTMATTER_DELIM}' frontmatter delimiters"
    )


def render_preset(template_text: str, persona: str) -> str:
    """Replace the placeholder line with the persona in a YAML literal block.

    The placeholder must sit alone on its own line; its leading whitespace
    defines the block indentation. Returns the fully rendered preset text.
    """
    out: list[str] = []
    replaced = False
    for line in template_text.splitlines(keepends=True):
        if not replaced and line.strip() == PLACEHOLDER:
            indent = line[: len(line) - len(line.lstrip())]
            for persona_line in persona.splitlines(keepends=True):
                if persona_line.strip() == "":
                    out.append("\n")
                else:
                    out.append(indent + persona_line)
            replaced = True
        else:
            out.append(line)
    if not replaced:
        raise ValueError(f"template does not contain a '{PLACEHOLDER}' placeholder line")
    return "".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    body_cmd = sub.add_parser("body", help="print the persona body (frontmatter stripped)")
    body_cmd.add_argument("--agent-md", required=True, type=Path, help="path to agents/<slug>.md")

    render_cmd = sub.add_parser("render", help="render the preset template with the persona injected")
    render_cmd.add_argument("--template", required=True, type=Path, help="preset agent.cordis.yml template")
    render_cmd.add_argument("--agent-md", required=True, type=Path, help="persona source agents/<slug>.md")
    render_cmd.add_argument("--out", required=True, type=Path, help="destination agent.cordis.yml")

    args = parser.parse_args(argv)

    if args.command == "body":
        sys.stdout.write(persona_body(args.agent_md.read_text(encoding="utf-8")))
        return 0

    persona = persona_body(args.agent_md.read_text(encoding="utf-8"))
    rendered = render_preset(args.template.read_text(encoding="utf-8"), persona)
    args.out.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
