#!/usr/bin/env python3
"""
Good First Issues Finder
Searches open source orgs for unassigned, no-PR good-first-issues,
reads full context (README, CONTRIBUTING, issue body), and presents
them for your approval before auto-commenting to request assignment.
"""

import os
import sys
import json
import time
import argparse
import requests
from datetime import datetime, timezone

# ── Config ──────────────────────────────────────────────────────────────────

ORGANIZATIONS = [
    # GSoC-participating orgs
    "python", "sympy", "scikit-learn", "matplotlib", "astropy",
    "openmrs", "fossasia", "processing", "sugar-labs",
    # CNCF / Cloud-native
    "kubernetes", "helm", "prometheus", "grafana", "fluxcd",
    "open-telemetry", "containerd",
    # Web / Frontend
    "vercel", "sveltejs", "vuejs", "nuxt", "vitejs",
    # Dev Tools
    "cli", "neovim", "prettier", "eslint",
    # AI / ML
    "huggingface", "pytorch", "tensorflow",
    # General open source
    "mozilla", "apache", "freedomofpress",
]

LABELS = ["good first issue", "good-first-issue", "beginner", "easy", "starter"]
MAX_ISSUES = 30          # max issues to fetch per run
MAX_COMMENTS_ON_ISSUE = 5  # skip noisy issues

COMMENT_TEMPLATE = """\
Hi @{maintainer} 👋

I'm Kiran Shams, a web developer and open source contributor (JavaScript / Python / GitHub automation).

I'd love to work on this issue! I've read through the issue description{contrib_note} and I have a clear idea of how to approach it.

Could you please assign this to me? I'll have a draft PR ready within a few days.

Thank you for maintaining this project! 🙏
"""


# ── GitHub API helpers ───────────────────────────────────────────────────────

class GitHub:
    BASE = "https://api.github.com"

    def __init__(self, token: str):
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def get(self, path: str, params: dict = None):
        url = f"{self.BASE}{path}"
        r = self.s.get(url, params=params)
        if r.status_code == 403 and "rate limit" in r.text.lower():
            reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(reset - int(time.time()), 1)
            print(f"  ⏳ Rate limited. Waiting {wait}s …")
            time.sleep(wait)
            r = self.s.get(url, params=params)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, body: dict):
        r = self.s.post(f"{self.BASE}{path}", json=body)
        r.raise_for_status()
        return r.json()

    def search_issues(self, query: str, per_page=30, page=1):
        return self.get("/search/issues", {
            "q": query, "per_page": per_page, "page": page, "sort": "created", "order": "desc"
        })

    def get_readme(self, owner: str, repo: str) -> str:
        try:
            data = self.get(f"/repos/{owner}/{repo}/readme")
            import base64
            return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")[:3000]
        except Exception:
            return ""

    def get_contributing(self, owner: str, repo: str) -> str:
        for path in ["CONTRIBUTING.md", "docs/CONTRIBUTING.md", ".github/CONTRIBUTING.md"]:
            try:
                data = self.get(f"/repos/{owner}/{repo}/contents/{path}")
                import base64
                return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")[:2000]
            except Exception:
                continue
        return ""

    def get_issue_comments_count(self, owner: str, repo: str, issue_number: int) -> int:
        try:
            data = self.get(f"/repos/{owner}/{repo}/issues/{issue_number}")
            return data.get("comments", 0)
        except Exception:
            return 999

    def has_open_pr(self, owner: str, repo: str, issue_number: int) -> bool:
        """Check if any open PR mentions this issue number."""
        try:
            prs = self.get(f"/repos/{owner}/{repo}/pulls", {"state": "open", "per_page": 20})
            for pr in prs:
                body = (pr.get("body") or "").lower()
                if f"#{issue_number}" in body or f"closes #{issue_number}" in body:
                    return True
        except Exception:
            pass
        return False

    def post_comment(self, owner: str, repo: str, issue_number: int, body: str):
        return self.post(f"/repos/{owner}/{repo}/issues/{issue_number}/comments", {"body": body})


# ── Issue finding ────────────────────────────────────────────────────────────

def build_query(org: str) -> str:
    label_part = " ".join(f'label:"{l}"' for l in LABELS)
    return (
        f"org:{org} is:issue is:open no:assignee "
        f'(label:"good first issue" OR label:"good-first-issue" OR label:"beginner" OR label:"easy")'
    )


def find_good_first_issues(gh: GitHub, orgs: list) -> list:
    results = []
    seen = set()

    print(f"\n🔍 Searching {len(orgs)} organizations …\n")

    for org in orgs:
        query = build_query(org)
        try:
            data = gh.search_issues(query, per_page=10)
            items = data.get("items", [])
            print(f"  {org}: {len(items)} candidates")

            for issue in items:
                url = issue["html_url"]
                if url in seen:
                    continue
                seen.add(url)

                # Skip if already has an assignee
                if issue.get("assignees") or issue.get("assignee"):
                    continue

                # Skip noisy issues
                if issue.get("comments", 0) > MAX_COMMENTS_ON_ISSUE:
                    continue

                repo_url = issue["repository_url"]
                parts = repo_url.rstrip("/").split("/")
                owner, repo = parts[-2], parts[-1]

                results.append({
                    "title": issue["title"],
                    "url": url,
                    "number": issue["number"],
                    "owner": owner,
                    "repo": repo,
                    "labels": [l["name"] for l in issue.get("labels", [])],
                    "comments": issue.get("comments", 0),
                    "body": (issue.get("body") or "")[:1000],
                    "created_at": issue["created_at"],
                    "user": issue["user"]["login"],
                })

                if len(results) >= MAX_ISSUES:
                    return results

            time.sleep(0.5)  # be polite

        except Exception as e:
            print(f"  ⚠️  {org}: {e}")

    return results


# ── Context fetching ─────────────────────────────────────────────────────────

def fetch_context(gh: GitHub, issue: dict) -> dict:
    owner, repo, number = issue["owner"], issue["repo"], issue["number"]
    print(f"\n📖 Reading context for: {issue['title'][:60]} …")

    readme = gh.get_readme(owner, repo)
    contributing = gh.get_contributing(owner, repo)
    has_pr = gh.has_open_pr(owner, repo, number)

    return {
        **issue,
        "readme_snippet": readme[:800] if readme else "(no README found)",
        "contributing_snippet": contributing[:600] if contributing else "(no CONTRIBUTING.md found)",
        "has_open_pr": has_pr,
        "has_contributing": bool(contributing),
    }


# ── Display ──────────────────────────────────────────────────────────────────

def display_issue(ctx: dict, index: int, total: int):
    print("\n" + "═" * 70)
    print(f"  Issue {index}/{total}")
    print("═" * 70)
    print(f"  📌 {ctx['title']}")
    print(f"  🔗 {ctx['url']}")
    print(f"  🏷  Labels : {', '.join(ctx['labels'])}")
    print(f"  💬 Comments: {ctx['comments']}")
    print(f"  🗓  Created : {ctx['created_at'][:10]}")
    print(f"  👤 Opened by: {ctx['user']}")
    if ctx.get("has_open_pr"):
        print("  ⚠️  WARNING: There may already be an open PR for this issue!")

    print("\n  📝 Issue Description:")
    body = ctx["body"].strip()
    print(textwrap_indent(body[:600] or "(no description)", "    "))

    print("\n  📚 README (excerpt):")
    print(textwrap_indent(ctx["readme_snippet"][:400], "    "))

    if ctx["has_contributing"]:
        print("\n  🤝 CONTRIBUTING.md (excerpt):")
        print(textwrap_indent(ctx["contributing_snippet"][:300], "    "))
    else:
        print("\n  ℹ️  No CONTRIBUTING.md found — check the repo directly.")

    print("═" * 70)


def textwrap_indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line for line in text.splitlines())


# ── Approval & comment ───────────────────────────────────────────────────────

def ask_approval(issue: dict) -> str:
    """Returns 'yes', 'skip', or 'quit'."""
    while True:
        choice = input(
            f"\n  👉 Comment on this issue to request assignment?\n"
            f"     [y] Yes, comment   [s] Skip   [q] Quit\n"
            f"  > "
        ).strip().lower()
        if choice in ("y", "yes"):
            return "yes"
        if choice in ("s", "skip", ""):
            return "skip"
        if choice in ("q", "quit"):
            return "quit"
        print("  Please enter y, s, or q.")


def post_assignment_comment(gh: GitHub, ctx: dict):
    contrib_note = (
        ", the README, and the CONTRIBUTING.md" if ctx["has_contributing"]
        else " and the README"
    )
    body = COMMENT_TEMPLATE.format(
        maintainer=ctx["user"],
        contrib_note=contrib_note,
    )

    print("\n  📨 Comment to be posted:")
    print(textwrap_indent(body, "    "))

    confirm = input("  Confirm post? [y/n]: ").strip().lower()
    if confirm not in ("y", "yes"):
        print("  ❌ Skipped (not confirmed).")
        return False

    try:
        gh.post_comment(ctx["owner"], ctx["repo"], ctx["number"], body)
        print(f"  ✅ Comment posted! → {ctx['url']}")
        return True
    except Exception as e:
        print(f"  ❌ Failed to post comment: {e}")
        return False


# ── Save results ─────────────────────────────────────────────────────────────

def save_results(issues: list, path: str = "found-issues.json"):
    with open(path, "w") as f:
        json.dump(issues, f, indent=2, default=str)
    print(f"\n💾 Results saved to {path}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Find and claim good-first-issues.")
    parser.add_argument("--token", default=os.environ.get("GH_TOKEN", ""),
                        help="GitHub personal access token (or set GH_TOKEN env var)")
    parser.add_argument("--orgs", nargs="*", help="Override organizations to search")
    parser.add_argument("--auto-comment", action="store_true",
                        help="Skip interactive approval (GitHub Actions mode)")
    parser.add_argument("--save", default="found-issues.json", help="Output JSON file")
    args = parser.parse_args()

    if not args.token:
        print("❌ No GitHub token. Set GH_TOKEN env var or use --token.")
        sys.exit(1)

    gh = GitHub(args.token)
    orgs = args.orgs or ORGANIZATIONS

    print("╔══════════════════════════════════════════════╗")
    print("║   🚀 Good First Issues Finder                ║")
    print("║   github.com/kiranShamsHere                  ║")
    print("╚══════════════════════════════════════════════╝")
    print(f"\n🏢 Searching {len(orgs)} organizations")
    print(f"🏷  Labels: good first issue, beginner, easy")
    print(f"🔒 Filter: no assignee + no open PR + <{MAX_COMMENTS_ON_ISSUE} comments")

    # Step 1: Find issues
    issues = find_good_first_issues(gh, orgs)

    if not issues:
        print("\n😔 No matching issues found. Try again later.")
        sys.exit(0)

    print(f"\n✅ Found {len(issues)} potential issues!")

    # Step 2: Interactive review
    approved = []
    for i, issue in enumerate(issues, 1):
        ctx = fetch_context(gh, issue)

        if ctx.get("has_open_pr"):
            print(f"\n  ⏭️  Skipping (has open PR): {issue['title'][:60]}")
            continue

        display_issue(ctx, i, len(issues))

        if args.auto_comment:
            # GitHub Actions mode — just save, don't comment
            approved.append(ctx)
        else:
            choice = ask_approval(ctx)
            if choice == "quit":
                print("\n👋 Quitting. Saving progress …")
                break
            elif choice == "yes":
                posted = post_assignment_comment(gh, ctx)
                if posted:
                    approved.append(ctx)

    # Step 3: Save results
    save_results(issues, args.save)

    print(f"\n🎉 Done! Commented on {len(approved)} issue(s).")
    for a in approved:
        print(f"   ✅ {a['url']}")


if __name__ == "__main__":
    main()