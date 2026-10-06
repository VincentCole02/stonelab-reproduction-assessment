#!/usr/bin/env python3
"""List candidate files for a reproduction assessment; do not infer runnability."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".tox", ".mypy_cache"}
MAX_FILES = 20_000
DISPLAY_LIMIT = 25
CATEGORIES = (
    "documentation",
    "license",
    "environment",
    "configuration",
    "entrypoints",
    "model_code",
    "data_code",
    "weights",
)
ENTRYPOINT_RE = re.compile(r"(^|[_-])(train|test|eval|evaluate|infer|inference|predict|demo|preprocess|prepare)([_-]|$)")


def categories_for(path: Path) -> set[str]:
    name = path.name.lower()
    stem = path.stem.lower()
    parts = {part.lower() for part in path.parts}
    found: set[str] = set()

    if name.startswith("readme") or name in {"citation.cff", "reproduce.md", "reproduction.md"}:
        found.add("documentation")
    if name.startswith(("license", "licence", "copying")):
        found.add("license")
    if (
        name.startswith(("requirements", "environment"))
        or name in {"pyproject.toml", "setup.py", "setup.cfg", "pipfile", "pipfile.lock", "poetry.lock", "uv.lock", "dockerfile", "conda-lock.yml"}
        or name.endswith("dockerfile")
    ):
        found.add("environment")
    if path.suffix.lower() in {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg"} and (
        "config" in parts or "configs" in parts or "config" in stem or "hparams" in stem
    ):
        found.add("configuration")
    if path.suffix.lower() in {".py", ".sh", ".ps1", ".ipynb"} and ENTRYPOINT_RE.search(stem):
        found.add("entrypoints")
    if path.suffix.lower() == ".py" and (
        "models" in parts or "model" in parts or "networks" in parts or "model" in stem or "network" in stem
    ):
        found.add("model_code")
    if path.suffix.lower() == ".py" and (
        "datasets" in parts or "dataset" in parts or "dataloader" in stem or "dataset" in stem or "preprocess" in stem
    ):
        found.add("data_code")
    if path.suffix.lower() in {".pt", ".pth", ".ckpt", ".safetensors", ".onnx", ".h5"}:
        found.add("weights")
    return found


def inspect(root: Path) -> dict:
    results: dict[str, list[str]] = {category: [] for category in CATEGORIES}
    count = 0
    truncated = False

    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not (Path(directory) / d).is_symlink())
        for filename in sorted(files):
            count += 1
            if count > MAX_FILES:
                truncated = True
                break
            absolute = Path(directory) / filename
            relative = absolute.relative_to(root)
            for category in categories_for(relative):
                results[category].append(relative.as_posix())
        if truncated:
            break

    return {"root": str(root), "files_scanned": min(count, MAX_FILES), "truncated": truncated, "candidates": results}


def render_markdown(result: dict) -> str:
    lines = [
        f"# Repository file inventory: {result['root']}",
        "",
        f"Scanned {result['files_scanned']} files" + (" (limit reached; inventory incomplete)." if result["truncated"] else "."),
        "Candidate names only. Open the files and trace the actual run path before drawing conclusions.",
    ]
    for category, paths in result["candidates"].items():
        lines.extend(["", f"## {category} ({len(paths)})"])
        lines.extend(f"- `{path}`" for path in paths[:DISPLAY_LIMIT])
        if len(paths) > DISPLAY_LIMIT:
            lines.append(f"- … {len(paths) - DISPLAY_LIMIT} more")
        if not paths:
            lines.append("- No filename candidates found; this does not prove the component is absent.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path, help="Path to an existing local repository checkout")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of Markdown")
    args = parser.parse_args()
    root = args.repository.resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")
    result = inspect(root)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render_markdown(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
