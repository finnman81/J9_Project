#!/usr/bin/env python3
"""
CI check: fail if dependency or build artifacts are tracked by git.
Run from project root: python scripts/check_repo_hygiene.py
"""
import subprocess
import sys

FORBIDDEN = ("node_modules", ".vite", "/dist/", "/build/", "dist-ssr/")


def main() -> int:
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        cwd=".",
    )
    if result.returncode != 0:
        print("git ls-files failed", file=sys.stderr)
        return 1
    tracked = result.stdout.strip().splitlines()
    bad = [p for p in tracked if any(f in p for f in FORBIDDEN)]
    if bad:
        print("Repository hygiene check failed: the following paths must not be tracked:", file=sys.stderr)
        for p in bad:
            print(" ", p, file=sys.stderr)
        print("Remove them with: git rm -r --cached <path> and ensure .gitignore rules are in place.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
