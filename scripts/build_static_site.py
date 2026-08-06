#!/usr/bin/env python3
"""Build a minimal GitHub Pages artifact instead of publishing the repository."""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_REFERENCE = re.compile(r'''(?:src|href)=["']([^"'#?]+)''')


def build(output: Path) -> dict[str, int]:
    resolved = output.resolve()
    if resolved in {ROOT, Path(resolved.anchor)}:
        raise ValueError("Static output must be a dedicated directory")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)

    html_files = sorted(ROOT.glob("*.html"))
    if not html_files or not (ROOT / "index.html").exists():
        raise FileNotFoundError("index.html is required")
    for path in html_files:
        shutil.copy2(path, resolved / path.name)
    for name in (".nojekyll",):
        source = ROOT / name
        if source.exists():
            shutil.copy2(source, resolved / name)
    for directory in ("src", "assets"):
        source = ROOT / directory
        if source.exists():
            shutil.copytree(source, resolved / directory)

    missing: list[str] = []
    local_references = 0
    for html in sorted(resolved.glob("*.html")):
        for reference in LOCAL_REFERENCE.findall(html.read_text(encoding="utf-8", errors="replace")):
            if reference.startswith(("http:", "https:", "mailto:", "javascript:", "data:")):
                continue
            local_references += 1
            if not (html.parent / reference).exists():
                missing.append(f"{html.name}: {reference}")
    if missing:
        raise FileNotFoundError("Missing local site references:\n" + "\n".join(missing))
    return {
        "html_files": len(html_files),
        "local_references": local_references,
        "files_published": sum(path.is_file() for path in resolved.rglob("*")),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="build/site")
    args = parser.parse_args()
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    print(build(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
