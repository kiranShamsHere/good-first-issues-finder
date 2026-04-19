#!/usr/bin/env python3
"""
Auto-comment script.
Reads your approval comment like "approve 23 36 37" and posts
assignment-request comments on those digest items.

The numbers refer to the item numbers in the Daily Digest issue
(1. Issue title, 2. Issue title, etc.) — NOT GitHub issue numbers.
"""

import os
import re
import sys
import json
import argparse
import requests

COMMENT_TEMPLATE = """\
Hi @{maintainer} 👋

I'm **Kiran Shams**, a web developer and open source contributor (JavaScript / Python / GitHub automation).

I'd love to work on this issue! I've read through the issue description{contrib_note} and I have a clear understanding of what needs to be done.

Could you please assign this to me? I'll have a draft PR ready within a few days. 

---
*Found via [good-first-issues-finder](https://github.com/kiranShamsHere/good-first-issues-finder)*
"""


class GitHub:
    BASE = "https://api.github.com"

    def __init__(self, token):
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        })

    def get(self, path):
        r = self.s.get(f"{self.BASE}{path}")
        r.raise_for_status()
        return r.json()

    def post_comment(self, owner, repo, number, body):
        r = self.s.post(
            f"{self.BASE}/repos/{owner}/{repo}/issues/{number}/comments",
            json={"body": body}
        )
        r.raise_for_status()
        return r.json()

    def has_contributing(self, owner, repo):
        for path in ["CONTRIBUTING.md", "docs/CONTRIBUTING.md", ".github/CONTRIBUTING.md"]:
            try:
                self.get(f"/repos/{owner}/{repo}/contents/{path}")
                return True
            except Exception:
                pass
        return False


def parse_indices(comment: str) -> list:
    """
    Parse digest item numbers from approval comment.
    Handles all formats:
      approve 23 36 37
      approve #23 #36 #37
      approve 23, 36, 37
    Returns list of integers (1-based digest indices).
    """
    # Remove the word 'approve' first
    text = re.sub(r'\bapprove\b', '', comment, flags=re.IGNORECASE)
    # Extract all numbers (with or without #)
    numbers = re.findall(r'#?(\d+)', text)
    return [int(n) for n in numbers if int(n) > 0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token",        required=True)
    parser.add_argument("--comment",      required=True,
                        help="The approval comment body e.g. 'approve 23 36 37'")
    parser.add_argument("--issues-file",  default="found-issues.json")
    args = parser.parse_args()

    # Load saved issues
    try:
        with open(args.issues_file) as f:
            all_issues = json.load(f)
    except FileNotFoundError:
        print(f"❌ Issues file not found: {args.issues_file}")
        sys.exit(1)

    if not all_issues:
        print("❌ Issues file is empty.")
        sys.exit(1)

    indices = parse_indices(args.comment)

    if not indices:
        print("⚠️  No numbers found in comment. Nothing to do.")
        print(f"   Comment was: {args.comment}")
        sys.exit(0)

    print(f"📋 Digest items to comment on: {indices}")
    print(f"📦 Total issues in digest: {len(all_issues)}")

    gh = GitHub(args.token)

    for idx in indices:
        # idx is 1-based (matching the "1. Title" numbering in the digest)
        if idx < 1 or idx > len(all_issues):
            print(f"\n⚠️  #{idx} is out of range (digest has 1–{len(all_issues)}), skipping.")
            continue

        issue = all_issues[idx - 1]  # convert to 0-based list index
        owner      = issue["owner"]
        repo       = issue["repo"]
        number     = issue["number"]
        maintainer = issue.get("user", "maintainer")

        print(f"\n🎯 Item #{idx}: {issue['title'][:60]}")
        print(f"   Repo   : {owner}/{repo}")
        print(f"   Issue  : #{number}")
        print(f"   URL    : {issue['url']}")

        has_contrib = gh.has_contributing(owner, repo)
        contrib_note = (
            ", the README, and the CONTRIBUTING.md" if has_contrib
            else " and the README"
        )

        body = COMMENT_TEMPLATE.format(
            maintainer=maintainer,
            contrib_note=contrib_note,
        )

        try:
            gh.post_comment(owner, repo, number, body)
            print(f"   ✅ Comment posted!")
        except Exception as e:
            print(f"   ❌ Failed to post comment: {e}")

    print("\n✅ Done!")


if __name__ == "__main__":
    main()