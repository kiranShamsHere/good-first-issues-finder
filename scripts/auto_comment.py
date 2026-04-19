#!/usr/bin/env python3
"""
Auto-comment script.
Reads your approval comment like "approve #3 #7" and posts
assignment-request comments on those issues.
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

**My plan:**
- Review the existing codebase around this issue
- Implement the fix/feature with proper tests
- Submit a clean PR following your contribution guidelines

Could you please assign this to me? I'll have a draft PR ready within a few days. 🙏

---
*Found via [good-first-issues-finder](https://github.com/kiranShamsHere/good-first-issues-finder)*
"""


class GitHub:
    BASE = "https://api.github.com"

    def __init__(self, token):
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"token {token}",
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

    def get_issue(self, owner, repo, number):
        return self.get(f"/repos/{owner}/{repo}/issues/{number}")

    def has_contributing(self, owner, repo):
        for path in ["CONTRIBUTING.md", "docs/CONTRIBUTING.md", ".github/CONTRIBUTING.md"]:
            try:
                self.get(f"/repos/{owner}/{repo}/contents/{path}")
                return True
            except Exception:
                pass
        return False


def parse_approved_indices(comment: str) -> list:
    """
    Parse indices from a comment like:
    'approve #3 #7' or 'approve 3, 7' or 'approve 3 7'
    Returns list of 1-based integers.
    """
    numbers = re.findall(r'#?(\d+)', comment)
    return [int(n) for n in numbers]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    parser.add_argument("--comment", required=True, help="The approval comment body")
    parser.add_argument("--issues-file", default="found-issues.json")
    args = parser.parse_args()

    # Load the saved issues
    try:
        with open(args.issues_file) as f:
            all_issues = json.load(f)
    except FileNotFoundError:
        print(f"❌ Issues file not found: {args.issues_file}")
        sys.exit(1)

    approved_indices = parse_approved_indices(args.comment)
    if not approved_indices:
        print("No issue indices found in the approval comment.")
        sys.exit(0)

    print(f"📋 Approved indices: {approved_indices}")
    gh = GitHub(args.token)

    for idx in approved_indices:
        if idx < 1 or idx > len(all_issues):
            print(f"⚠️  Index {idx} out of range (1–{len(all_issues)}), skipping.")
            continue

        issue = all_issues[idx - 1]
        owner = issue["owner"]
        repo = issue["repo"]
        number = issue["number"]
        maintainer = issue.get("user", "maintainer")

        print(f"\n🎯 Processing: {issue['title'][:60]}")
        print(f"   {issue['url']}")

        # Check for CONTRIBUTING.md
        has_contrib = gh.has_contributing(owner, repo)
        contrib_note = (
            ", the README, and the CONTRIBUTING.md" if has_contrib
            else " and the README"
        )

        # Build comment
        body = COMMENT_TEMPLATE.format(
            maintainer=maintainer,
            contrib_note=contrib_note,
        )

        try:
            gh.post_comment(owner, repo, number, body)
            print(f"   ✅ Comment posted!")
        except Exception as e:
            print(f"   ❌ Failed: {e}")

    print("\n✅ Done!")


if __name__ == "__main__":
    main()