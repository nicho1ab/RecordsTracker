"""Render and preflight repository-governed pull-request evidence bodies."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_independent_verification as verification

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"


def _changed_files_from_git(base: str) -> list[str]:
    commands = (
        ("git", "diff", "--name-only", "--merge-base", base, "HEAD"),
        ("git", "diff", "--name-only"),
        ("git", "diff", "--cached", "--name-only"),
        ("git", "ls-files", "--others", "--exclude-standard"),
    )
    files: dict[str, None] = {}
    for command in commands:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if line.strip():
                files.setdefault(line.strip(), None)
    return list(files)


def _print_violations(violations: list[str]) -> int:
    if violations:
        print("Independent verification failed:")
        for violation in violations:
            print(f"- {violation}")
        return 1
    print("Independent verification passed.")
    return 0


def render_body(output: Path) -> int:
    output.write_text(TEMPLATE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Wrote PR evidence template to {output}")
    return 0


def preflight_body(
    *,
    body_path: Path,
    changed_files_path: Path | None,
    base: str,
    repo_root: Path,
) -> int:
    body = body_path.read_text(encoding="utf-8")
    changed_files = (
        verification._changed_files(changed_files_path)
        if changed_files_path is not None
        else _changed_files_from_git(base)
    )
    return _print_violations(
        verification.find_verification_violations(repo_root, body, changed_files)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    render = subparsers.add_parser("render", help="copy the authoritative PR template")
    render.add_argument("--output", type=Path, required=True)
    preflight = subparsers.add_parser(
        "preflight", help="validate a proposed body with the same rules as CI"
    )
    preflight.add_argument("--body", type=Path, required=True)
    preflight.add_argument("--changed-files", type=Path)
    preflight.add_argument("--base", default="origin/main")
    preflight.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    if args.command == "render":
        return render_body(args.output)
    return preflight_body(
        body_path=args.body,
        changed_files_path=args.changed_files,
        base=args.base,
        repo_root=args.repo_root,
    )


if __name__ == "__main__":
    raise SystemExit(main())
