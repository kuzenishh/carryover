#!/usr/bin/env python3
"""carryover - stop re-teaching your coding agent the same thing every session.

Single file, no dependencies. Keeps a small, durable memory of the corrections,
dead ends and decisions from your agent sessions, and prints them back at the
start of the next one.
"""

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

VERSION = "0.1.0"
DIR = ".carryover"
MEMORY = "memory.json"
MAX_LESSONS = 60

KINDS = ("rule", "deadend", "decision")

# Phrases people actually type when the agent got it wrong. Ordered by how
# strong a signal they are.
CORRECTION_PATTERNS = [
    (r"\bno,? not like that\b", "rule"),
    (r"\bstop (doing|using|adding|creating)\b", "rule"),
    (r"\b(don'?t|do not) (ever )?(use|add|create|touch|modify|rewrite|refactor)\b", "rule"),
    (r"\bnever (use|add|call|touch|commit|push)\b", "rule"),
    (r"\bthat'?s (not|wrong|incorrect)\b", "rule"),
    (r"\bi (already )?(told|said) you\b", "rule"),
    (r"\b(we|i) (already |previously )?tried\b", "deadend"),
    (r"\bthat (didn'?t|does not|doesn'?t) work\b", "deadend"),
    (r"\bbroke (prod|production|the build)\b", "deadend"),
    (r"\b(we'?re|we are|let'?s) (going with|using|sticking with)\b", "decision"),
    (r"\bwe decided\b", "decision"),
    (r"\buse .{2,40} instead\b", "decision"),
]

BANNER = "<!-- carryover: agent memory for this project -->"


def root(start: Path = None) -> Path:
    """Nearest ancestor holding .carryover, else cwd."""
    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        if (p / DIR).is_dir():
            return p
    return cur


def store_path(base: Path) -> Path:
    return base / DIR / MEMORY


def load(base: Path) -> dict:
    p = store_path(base)
    if not p.exists():
        return {"version": VERSION, "lessons": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        sys.exit(f"carryover: cannot read {p}: {exc}")


def save(base: Path, data: dict) -> None:
    p = store_path(base)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().rstrip(".").lower()


def add_lesson(data: dict, text: str, kind: str, source: str = "manual") -> bool:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return False
    if len(text) > 240:
        text = text[:237].rstrip() + "..."
    key = normalize(text)
    for l in data["lessons"]:
        if normalize(l["text"]) == key:
            l["hits"] = l.get("hits", 1) + 1
            l["last_seen"] = date.today().isoformat()
            return False
    data["lessons"].append({
        "text": text,
        "kind": kind if kind in KINDS else "rule",
        "source": source,
        "hits": 1,
        "added": date.today().isoformat(),
        "last_seen": date.today().isoformat(),
    })
    return True


def extract(lines) -> list:
    """Pull candidate lessons out of human turns of a transcript."""
    found = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        for pattern, kind in CORRECTION_PATTERNS:
            if re.search(pattern, s, re.I):
                found.append((s, kind))
                break
    return found


def read_turns(path: Path) -> list:
    """Yield human-authored text from a .jsonl session log or a plain text file."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    out = []
    if path.suffix == ".jsonl":
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = obj.get("message", obj)
            if msg.get("role") != "user":
                continue
            content = msg.get("content")
            if isinstance(content, str):
                out.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        out.append(part.get("text", ""))
        return out
    # plain text: treat every line as a candidate
    return raw.splitlines()


def render(data: dict, limit: int = MAX_LESSONS) -> str:
    lessons = sorted(
        data["lessons"],
        key=lambda l: (-l.get("hits", 1), l.get("last_seen", "")),
    )[:limit]
    if not lessons:
        return BANNER + "\n\n(nothing learned yet)\n"
    buckets = {k: [l for l in lessons if l["kind"] == k] for k in KINDS}
    titles = {
        "rule": "Rules (learned the hard way)",
        "deadend": "Dead ends (already tried, did not work)",
        "decision": "Decisions (settled, do not relitigate)",
    }
    parts = [BANNER, "", "# Project memory", ""]
    for kind in KINDS:
        items = buckets[kind]
        if not items:
            continue
        parts.append(f"## {titles[kind]}")
        for l in items:
            mark = f"  (hit {l['hits']}x)" if l.get("hits", 1) > 1 else ""
            parts.append(f"- {l['text']}{mark}")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# commands


def cmd_init(args):
    base = Path.cwd()
    (base / DIR).mkdir(exist_ok=True)
    data = load(base)
    save(base, data)

    claude_md = base / "CLAUDE.md"
    pointer = (
        "\n## Project memory\n"
        "Run the carryover brief command and follow everything it prints. "
        "Those are corrections from earlier sessions. Do not repeat them.\n"
    )
    if claude_md.exists():
        if "carryover brief" not in claude_md.read_text(encoding="utf-8"):
            with claude_md.open("a", encoding="utf-8") as fh:
                fh.write(pointer)
            print("carryover: appended pointer to CLAUDE.md")
    else:
        claude_md.write_text("# CLAUDE.md" + pointer, encoding="utf-8")
        print("carryover: created CLAUDE.md")
    print(f"carryover: initialised in {base / DIR}")


def cmd_add(args):
    base = root()
    data = load(base)
    if add_lesson(data, " ".join(args.text), args.kind):
        save(base, data)
        print(f"carryover: remembered ({args.kind})")
    else:
        save(base, data)
        print("carryover: already knew that")


def cmd_learn(args):
    base = root()
    data = load(base)
    path = Path(args.path)
    if not path.exists():
        sys.exit(f"carryover: no such file: {path}")
    candidates = extract(read_turns(path))
    if not candidates:
        print("carryover: nothing worth keeping in that session")
        return
    kept = 0
    for text, kind in candidates:
        if args.yes:
            keep = True
        else:
            print(f"\n  [{kind}] {text}")
            keep = input("  keep? [y/N] ").strip().lower().startswith("y")
        if keep and add_lesson(data, text, kind, source=path.name):
            kept += 1
    save(base, data)
    print(f"\ncarryover: learned {kept} new, {len(candidates)} candidates seen")


def cmd_brief(args):
    base = root()
    sys.stdout.write(render(load(base)))


def cmd_list(args):
    base = root()
    data = load(base)
    if not data["lessons"]:
        print("carryover: empty")
        return
    for i, l in enumerate(data["lessons"]):
        print(f"{i:>3}  [{l['kind']:<8}] {l['text']}")


def cmd_forget(args):
    base = root()
    data = load(base)
    try:
        gone = data["lessons"].pop(args.index)
    except IndexError:
        sys.exit(f"carryover: no lesson at index {args.index}")
    save(base, data)
    print(f"carryover: forgot {gone['text']!r}")


def build_parser():
    p = argparse.ArgumentParser(
        prog="carryover",
        description="Stop re-teaching your coding agent the same thing every session.",
    )
    p.add_argument("--version", action="version", version=f"carryover {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="set up carryover in this project").set_defaults(fn=cmd_init)

    a = sub.add_parser("add", help="remember a lesson by hand")
    a.add_argument("text", nargs="+")
    a.add_argument("--kind", choices=KINDS, default="rule")
    a.set_defaults(fn=cmd_add)

    l = sub.add_parser("learn", help="pull lessons out of a session transcript")
    l.add_argument("path", help=".jsonl session log or plain text")
    l.add_argument("-y", "--yes", action="store_true", help="keep everything, no prompts")
    l.set_defaults(fn=cmd_learn)

    sub.add_parser("brief", help="print the memory block for a new session").set_defaults(fn=cmd_brief)
    sub.add_parser("list", help="list lessons with indexes").set_defaults(fn=cmd_list)

    f = sub.add_parser("forget", help="drop a lesson by index")
    f.add_argument("index", type=int)
    f.set_defaults(fn=cmd_forget)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
