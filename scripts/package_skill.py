#!/usr/bin/env python3
"""Build a deterministic, clean ai-commerce-video .skill archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from audit_release import audit


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT_NAME = "ai-commerce-video"
REPO_ONLY_TOP_LEVEL = {
    ".git",
    ".github",
    ".gitignore",
    "README.md",
    "README.zh-CN.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "tests",
    "dist",
}
RELEASE_TOOL_PATHS = {
    Path("scripts/audit_release.py"),
    Path("scripts/package_skill.py"),
}
FORBIDDEN_PARTS = {"__pycache__", ".pytest_cache", "projects", "outputs", "clips", "requests", ".stitch_tmp"}
FORBIDDEN_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".env",
    ".mp4",
    ".mov",
    ".webm",
    ".mkv",
    ".wav",
    ".mp3",
    ".srt",
    ".vtt",
    ".log",
}
FIXED_TIMESTAMP = (2026, 1, 1, 0, 0, 0)


def package_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if relative.parts[0] in REPO_ONLY_TOP_LEVEL:
            continue
        if relative in RELEASE_TOOL_PATHS:
            continue
        if any(part in FORBIDDEN_PARTS for part in relative.parts):
            continue
        if path.suffix.lower() in FORBIDDEN_SUFFIXES or path.name in {".DS_Store", ".env.local"}:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_archive(root: Path, output: Path) -> list[str]:
    output.parent.mkdir(parents=True, exist_ok=True)
    names = []
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in package_files(root):
            relative = path.relative_to(root).as_posix()
            name = f"{PACKAGE_ROOT_NAME}/{relative}"
            info = zipfile.ZipInfo(name, FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.stat().st_mode & 0o111 else 0o644) << 16
            archive.writestr(info, path.read_bytes())
            names.append(name)
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(REPO_ROOT), help="Repository root")
    parser.add_argument("--output", default="dist/ai-commerce-video.skill", help="Output .skill path")
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    output = Path(args.output).expanduser()
    if not output.is_absolute():
        output = (root / output).resolve()

    audit_report = audit(root)
    if not audit_report["ok"]:
        print(json.dumps({"ok": False, "audit": audit_report}, ensure_ascii=False, indent=2))
        return 1

    names = write_archive(root, output)
    required = {
        f"{PACKAGE_ROOT_NAME}/SKILL.md",
        f"{PACKAGE_ROOT_NAME}/LICENSE",
        f"{PACKAGE_ROOT_NAME}/scripts/prepare_project.py",
    }
    missing = sorted(required.difference(names))
    if missing:
        output.unlink(missing_ok=True)
        print(json.dumps({"ok": False, "error": f"Archive missing required files: {missing}"}, ensure_ascii=False, indent=2))
        return 1

    report = {
        "ok": True,
        "output": str(output),
        "file_count": len(names),
        "size_bytes": output.stat().st_size,
        "sha256": sha256_file(output),
        "audit_warnings": audit_report["warnings"],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
