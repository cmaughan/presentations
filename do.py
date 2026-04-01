#!/usr/bin/env python3
"""Build helper for presentations repo."""
from __future__ import annotations

import pathlib
import subprocess
import sys


def repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent


def find_presentations(root: pathlib.Path) -> list[pathlib.Path]:
    """Return directories that contain a Quarto presentation."""
    results = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "index.qmd").exists():
            results.append(child)
    return results


def needs_build(pres: pathlib.Path) -> bool:
    """True if the output is missing or older than any source file."""
    output = pres / "_output" / "index.html"
    if not output.exists():
        return True
    out_mtime = output.stat().st_mtime
    for src in pres.rglob("*"):
        if src.is_file() and "_output" not in src.parts and ".quarto" not in src.parts:
            if src.stat().st_mtime > out_mtime:
                return True
    return False


def run(command: list[str], cwd: pathlib.Path) -> int:
    print("> " + " ".join(command))
    return subprocess.run(command, cwd=cwd, check=False).returncode


def build(pres: pathlib.Path, force: bool = False) -> int:
    if not force and not needs_build(pres):
        print(f"  [{pres.name}] up to date")
        return 0
    return run(["quarto", "render", str(pres / "index.qmd")], pres)


def help_text(presentations: list[pathlib.Path]) -> str:
    names = ", ".join(p.name for p in presentations) if presentations else "(none found)"
    return f"""Usage:
  python do.py <command> [presentation]

Commands:
  slides [name]          Build a presentation (default: all)
  slides-preview [name]  Build if needed, then live-preview in browser
  slides-pdf [name]      Export a presentation to PDF

Available presentations: {names}

If [name] is omitted, the command applies to all presentations.

Examples:
  python do.py slides
  python do.py slides-preview slurp_and_learn
  python do.py slides-pdf slurp_and_learn
"""


def resolve_target(root: pathlib.Path, presentations: list[pathlib.Path], name: str | None) -> list[pathlib.Path]:
    if name is None:
        return presentations
    target = root / name
    if target in presentations:
        return [target]
    print(f"Unknown presentation: {name}")
    print(f"Available: {', '.join(p.name for p in presentations)}")
    sys.exit(1)


def main() -> int:
    root = repo_root()
    presentations = find_presentations(root)
    args = sys.argv[1:]

    if not args or args[0] in {"-h", "--help", "help"}:
        print(help_text(presentations))
        return 0

    command = args[0].lower()
    name = args[1] if len(args) > 1 else None

    if command == "slides":
        targets = resolve_target(root, presentations, name)
        for pres in targets:
            rc = build(pres, force=True)
            if rc != 0:
                return rc
        return 0

    if command == "slides-preview":
        targets = resolve_target(root, presentations, name)
        if len(targets) != 1:
            if len(targets) == 1:
                pass
            else:
                print("Preview requires a single presentation name.")
                print(f"Available: {', '.join(p.name for p in presentations)}")
                return 1
        pres = targets[0]
        rc = build(pres)
        if rc != 0:
            return rc
        return run(["quarto", "preview", str(pres / "index.qmd")], pres)

    if command == "slides-pdf":
        targets = resolve_target(root, presentations, name)
        for pres in targets:
            rc = run(["quarto", "render", str(pres / "index.qmd"), "--to", "pdf"], pres)
            if rc != 0:
                return rc
        return 0

    print(f"Unknown command: {command}\n")
    print(help_text(presentations))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
