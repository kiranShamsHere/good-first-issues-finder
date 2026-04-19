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

# ── Config ────────────────────────────────────────────────────────────────────

ORGANIZATIONS = [
    "python", "sympy", "scikit-learn", "matplotlib", "astropy",
    "openmrs", "fossasia", "processing",
    "kubernetes", "helm", "prometheus", "grafana", "fluxcd",
    "open-telemetry", "containerd",
    "vercel", "sveltejs", "vuejs", "nuxt", "vitejs",
    "cli", "prettier", "eslint",
    "huggingface", "pytorch", "tensorflow",
    "mozilla", "apache",
]

# Search each label separately — GitHub API does NOT support OR in label queries reliably
LABEL_QUERIES = [
    "good first issue",
    "good-first-issue",
    "beginner friendly",
    "easy",
]

MAX_ISSUES        = 40
MAX_COMMENTS      = 5   # skip issues with too many comments (probably being worked on)
SLEEP_BETWEEN     = 0.8 # seconds between API calls to avoid rate limits

COMMENT_TEMPLATE = """\
Hi @{maintainer} 👋

I'm **Kiran Shams**, a web developer and open source contributor \
(JavaScript / Python / GitHub automation).

I'd love to work on this issue! I've read through the issue description{contrib_note} \
and I have a clear idea of how to approach it.

Could you please assign this to me? I'll have a draft PR ready within a few days.

Thank you for maintaining this project! 🙏

---
*Found via [good-first-issues-finder](https://github.com/kiranShamsHere/good-first-issues-finder)*
"""


# ── GitHub API ────────────────────────────────────────────────────────────────

class GitHub:
    BASE = "https://api.github.com"

    def __init__(self, token: str):
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def get(self, path: str, params: dict = None):
        url = f"{self.BASE}{path}"
        for attempt in range(3):
            r = self.s.get(url, params=params)
            if r.status_code == 403:
                reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait  = max(reset - int(time.time()), 5)
                print(f"  ⏳ Rate limited — waiting {wait}s …")
                time.sleep(wait)
                continue
            if r.status_code == 422:
                # Unprocessable query — return empty gracefully
                return {}
            r.raise_for_status()
            return r.json()
        return {}

    def search(self, q: str, per_page: int = 10):
        data = self.get("/search/issues", {
            "q": q,
            "sort": "created",
            "order": "desc",
            "per_page": per_page,
        })
        return data.get("items", [])

    def post_comment(self, owner, repo, number, body):
        r = self.s.post(
            f"{self.BASE}/repos/{owner}/{repo}/issues/{number}/comments",
            json={"body": body}
        )
        r.raise_for_status()
        return r.json()

    def get_readme(self, owner, repo) -> str:
        try:
            import base64
            data = self.get(f"/repos/{owner}/{repo}/readme")
            return base64.b64decode(data.get("content", "")).decode("utf-8", errors="ignore")[:2000]
        except Exception:
            return ""

    def get_contributing(self, owner, repo) -> str:
        for path in ["CONTRIBUTING.md", "docs/CONTRIBUTING.md", ".github/CONTRIBUTING.md"]:
            try:
                import base64
                data = self.get(f"/repos/{owner}/{repo}/contents/{path}")
                return base64.b64decode(data.get("content", "")).decode("utf-8", errors="ignore")[:1500]
            except Exception:
                continue
        return ""

    def has_open_pr(self, owner, repo, issue_number) -> bool:
        """Check if any open PR references this issue."""
        try:
            prs = self.get(f"/repos/{owner}/{repo}/pulls", {"state": "open", "per_page": 30})
            for pr in (prs or []):
                body = (pr.get("body") or "").lower()
                title = (pr.get("title") or "").lower()
                if f"#{issue_number}" in body or f"#{issue_number}" in title:
                    return True
        except Exception:
            pass
        return False


# ── Searching ─────────────────────────────────────────────────────────────────

def find_issues(gh: GitHub, orgs: list) -> list:
    results = []
    seen    = set()

    print(f"\n🔍 Searching {len(orgs)} orgs across {len(LABEL_QUERIES)} label types …\n")

    for org in orgs:
        org_count = 0
        for label in LABEL_QUERIES:
            # Simple, reliable query format
            query = f'org:{org} is:issue is:open no:assignee label:"{label}"'
            try:
                items = gh.search(query, per_page=10)
            except Exception as e:
                print(f"  ⚠ {org} [{label}]: {e}")
                time.sleep(SLEEP_BETWEEN)
                continue

            for issue in items:
                url = issue.get("html_url", "")
                if not url or url in seen:
                    continue
                seen.add(url)

                # Skip if it already has an assignee (double-check)
                if issue.get("assignees") or issue.get("assignee"):
                    continue

                # Skip if too many comments already
                if issue.get("comments", 0) > MAX_COMMENTS:
                    continue

                repo_url = issue.get("repository_url", "")
                parts = repo_url.rstrip("/").split("/")
                if len(parts) < 2:
                    continue
                owner, repo = parts[-2], parts[-1]

                results.append({
                    "title":      issue["title"],
                    "url":        url,
                    "number":     issue["number"],
                    "owner":      owner,
                    "repo":       repo,
                    "labels":     [l["name"] for l in issue.get("labels", [])],
                    "comments":   issue.get("comments", 0),
                    "body":       (issue.get("body") or "")[:800],
                    "created_at": issue.get("created_at", ""),
                    "user":       issue["user"]["login"],
                })
                org_count += 1

                if len(results) >= MAX_ISSUES:
                    print(f"  {org}: {org_count} issues  (reached max {MAX_ISSUES})")
                    return results

            time.sleep(SLEEP_BETWEEN)

        if org_count:
            print(f"  ✅ {org}: {org_count} issues")
        else:
            print(f"  — {org}: 0 matching issues")

    return results


# ── Context ───────────────────────────────────────────────────────────────────

def fetch_context(gh: GitHub, issue: dict) -> dict:
    owner, repo, number = issue["owner"], issue["repo"], issue["number"]
    readme       = gh.get_readme(owner, repo)
    contributing = gh.get_contributing(owner, repo)
    has_pr       = gh.has_open_pr(owner, repo, number)
    return {
        **issue,
        "readme_snippet":       readme[:600]       if readme       else "(no README)",
        "contributing_snippet": contributing[:400] if contributing else "(no CONTRIBUTING.md)",
        "has_open_pr":          has_pr,
        "has_contributing":     bool(contributing),
    }


# ── Display ───────────────────────────────────────────────────────────────────

def indent(text: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + line for line in str(text).splitlines())

def display(ctx: dict, i: int, total: int):
    print("\n" + "═" * 68)
    print(f"  Issue {i}/{total}")
    print("═" * 68)
    print(f"  📌  {ctx['title']}")
    print(f"  🔗  {ctx['url']}")
    print(f"  🏷   Labels : {', '.join(ctx['labels'])}")
    print(f"  💬  Comments: {ctx['comments']}")
    print(f"  🗓   Created : {ctx['created_at'][:10]}")
    print(f"  👤  Opened by: {ctx['user']}")
    if ctx.get("has_open_pr"):
        print("  ⚠️   WARNING: an open PR may already exist!")
    print("\n  📝 Description:")
    print(indent((ctx["body"] or "(none)")[:500]))
    print("\n  📚 README (excerpt):")
    print(indent(ctx["readme_snippet"][:300]))
    if ctx["has_contributing"]:
        print("\n  🤝 CONTRIBUTING.md (excerpt):")
        print(indent(ctx["contributing_snippet"][:200]))
    print("═" * 68)


# ── Approval & comment ────────────────────────────────────────────────────────

def ask(ctx: dict) -> str:
    while True:
        c = input("\n  Comment to request assignment? [y] Yes  [s] Skip  [q] Quit\n  > ").strip().lower()
        if c in ("y", "yes"):   return "yes"
        if c in ("s", "skip", ""): return "skip"
        if c in ("q", "quit"):  return "quit"

def post_comment(gh: GitHub, ctx: dict) -> bool:
    note = (", the README, and the CONTRIBUTING.md"
            if ctx["has_contributing"] else " and the README")
    body = COMMENT_TEMPLATE.format(maintainer=ctx["user"], contrib_note=note)
    print("\n  📨 Comment preview:")
    print(indent(body))
    if input("  Confirm? [y/n]: ").strip().lower() not in ("y", "yes"):
        print("  ❌ Skipped.")
        return False
    try:
        gh.post_comment(ctx["owner"], ctx["repo"], ctx["number"], body)
        print(f"  ✅ Posted → {ctx['url']}")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token",        default=os.environ.get("GH_TOKEN", ""))
    parser.add_argument("--orgs",         nargs="*")
    parser.add_argument("--auto-comment", action="store_true",
                        help="GitHub Actions mode: save results, skip interactive prompts")
    parser.add_argument("--save",         default="found-issues.json")
    args = parser.parse_args()

    if not args.token:
        print("❌  No token. Set GH_TOKEN or use --token.")
        sys.exit(1)

    gh   = GitHub(args.token)
    orgs = args.orgs or ORGANIZATIONS

    print("╔══════════════════════════════════════════╗")
    print("║  🚀 Good First Issues Finder             ║")
    print("╚══════════════════════════════════════════╝")

    issues   = find_issues(gh, orgs)
    approved = []

    print(f"\n✅ Found {len(issues)} issue(s) total.")

    if not issues:
        print("😔 Nothing found this run — try again later or broaden orgs.")
        # Still write empty file so workflow doesn't fail
        with open(args.save, "w") as f:
            json.dump([], f)
        sys.exit(0)

    # Save immediately
    with open(args.save, "w") as f:
        json.dump(issues, f, indent=2, default=str)
    print(f"💾 Saved to {args.save}")

    if args.auto_comment:
        print("ℹ️  Auto-comment mode — skipping interactive review.")
        return

    # Interactive review
    for i, issue in enumerate(issues, 1):
        ctx    = fetch_context(gh, issue)
        if ctx.get("has_open_pr"):
            print(f"\n⏭️  Skipping (open PR exists): {issue['title'][:60]}")
            continue
        display(ctx, i, len(issues))
        choice = ask(ctx)
        if choice == "quit":
            print("\n👋 Quitting.")
            break
        if choice == "yes":
            if post_comment(gh, ctx):
                approved.append(ctx)

    print(f"\n🎉 Done! Commented on {len(approved)} issue(s).")
    for a in approved:
        print(f"   ✅ {a['url']}")


if __name__ == "__main__":
    main()