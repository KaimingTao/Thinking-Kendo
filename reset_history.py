#!/usr/bin/env python3
import argparse
import subprocess
import sys


def run(cmd, *, capture=False):
    if capture:
        result = subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE)
        return result.stdout.strip()
    subprocess.run(cmd, check=True)
    return ""


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Rewrite git history by creating a new initial commit and force-pushing it."
        )
    )
    parser.add_argument(
        "--remote",
        default="origin",
        help="Remote name to push to (default: origin).",
    )
    parser.add_argument(
        "--branch",
        default="",
        help="Branch name to rewrite (default: current branch).",
    )
    parser.add_argument(
        "--message",
        default="Initial commit",
        help="Commit message to use (default: Initial commit).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt.",
    )
    args = parser.parse_args()

    branch = args.branch or run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture=True)

    if not args.yes:
        prompt = (
            f"This will rewrite history of {branch} and force-push to "
            f"{args.remote}/{branch}. Continue? [y/N] "
        )
        reply = input(prompt).strip().lower()
        if reply not in {"y", "yes"}:
            print("Aborted.")
            return 1

    temp_branch = f"{branch}-orphan"

    run(["git", "checkout", "--orphan", temp_branch])
    run(["git", "add", "-A"])
    run(["git", "commit", "-m", args.message])
    run(["git", "branch", "-D", branch])
    run(["git", "branch", "-m", branch])
    run(["git", "push", "--force", args.remote, branch])
    return 0


if __name__ == "__main__":
    sys.exit(main())
