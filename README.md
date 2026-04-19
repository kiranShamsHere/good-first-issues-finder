# 🚀 Good First Issues Finder

> **Automatically find unassigned, no-PR good-first-issues from top open source organizations — delivered to your inbox daily. Review them, then comment to request assignment.**

Built by [Kiran Shams](https://github.com/kiranShamsHere) · Web Developer & Open Source Contributor

---

## ✨ What This Does

Every day at 6 AM UTC (11 AM PKT), this workflow:

1. **Searches 30+ organizations** (GSoC orgs, CNCF, Kubernetes, Vercel, HuggingFace, etc.)
2. **Filters strictly** — only issues with:
   - `good first issue` / `beginner` / `easy` label
   - No assignee
   - No open pull request
   - Fewer than 5 comments (not too noisy)
3. **Reads full context** — fetches README and CONTRIBUTING.md for each repo
4. **Creates a Daily Digest issue** in this repo with all found issues listed
5. **Waits for YOUR approval** — you reply `approve 3 7` to the digest
6. **Auto-posts a professional comment** on those issues requesting assignment

> **Note:** Auto-commenting works on open repos (fossasia, processing, sympy, etc.).
> Large orgs like Helm or Kubernetes restrict external comments — comment manually on those.
> Either way, the real value is the **automated daily search** that saves you 1-2 hours every day.

---

## 🏗 Repository Structure

```
good-first-issues-finder/
├── .github/
│   └── workflows/
│       ├── find-issues.yml       # Daily search + digest creator
│       └── auto-comment.yml      # Posts comment when you approve
├── scripts/
│   ├── find_issues.py            # Core search engine
│   └── auto_comment.py           # Comment poster
├── found-issues.json             # Latest results (auto-updated daily)
├── requirements.txt
└── README.md
```

---

## ⚙️ Setup (5 minutes)

### Step 1: Clone the repo
```bash
git clone https://github.com/kiranShamsHere/good-first-issues-finder.git
cd good-first-issues-finder
```

### Step 2: Create a GitHub Personal Access Token
1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens**
2. Create a token with:
   - **Repository permissions:** Issues (Read & Write), Contents (Read & Write)
   - **Resource access:** All repositories
3. Copy the token — you won't see it again

### Step 3: Add the token as a secret
1. Go to your repo → **Settings → Secrets and variables → Actions**
2. Click **New repository secret**
3. Name: `GH_TOKEN` · Value: your token
4. Click **Add secret**

### Step 4: Enable Actions
Go to **Actions tab → Enable workflows**

### Step 5: Test it manually
Go to **Actions → Find Good First Issues → Run workflow**

---

## 🎯 Daily Workflow

```
6 AM UTC (auto) or manual trigger
         ↓
Searches 30+ orgs via GitHub API
         ↓
Filters: good-first-issue + no assignee + no open PR
         ↓
Reads README + CONTRIBUTING.md for each repo
         ↓
Creates "Daily Digest" issue in THIS repo
         ↓
You read through the digest (takes 5 minutes)
         ↓
Reply: "approve 3 7"  ← plain numbers, no #
         ↓
Bot posts professional comment on those issues
         ↓
Maintainers assign you → you start contributing! 🎉
```

---

## 💬 How to Approve Issues

When you get a digest issue, it looks like this:

```
### 36. Fix comment in tutorial
- 🔗 URL: https://github.com/processing/p5.js-website/issues/1319
- 🏷 Labels: Documentation, Good First Issue
- 💬 Comments: 2
- 📅 Created: 2026-04-08
```

To request assignment on items 36 and 37, reply on the digest issue:

```
approve 36 37
```

> ⚠️ Use plain numbers only — no `#` symbol

The bot will post this on your behalf:

> Hi @maintainer 👋
>
> I'm **Kiran Shams**, a web developer and open source contributor (JavaScript / Python / GitHub automation).
>
> I'd love to work on this issue! I've read through the issue description, the README, and the CONTRIBUTING.md and I have a clear understanding of what needs to be done.
>
> Could you please assign this to me? I'll have a draft PR ready within a few days. 🙏

---

## 🖥 Local Usage

Run interactively on your own machine:

```bash
# Install dependencies
pip install -r requirements.txt

# Run interactively (asks you before each comment)
export GH_TOKEN=your_token_here
python scripts/find_issues.py

# Search specific orgs only
python scripts/find_issues.py --orgs fossasia processing sympy

# Save results without commenting (GitHub Actions mode)
python scripts/find_issues.py --auto-comment
```

---

## 🏢 Organizations Searched

| Category | Organizations |
|----------|--------------|
| **GSoC** | python, sympy, scikit-learn, matplotlib, astropy, fossasia |
| **CNCF** | kubernetes, helm, prometheus, grafana, fluxcd, open-telemetry |
| **Web** | vercel, sveltejs, vuejs, nuxt, vitejs |
| **Dev Tools** | cli (GitHub CLI), prettier, eslint |
| **AI/ML** | huggingface, pytorch, tensorflow |
| **General** | mozilla, apache, freedomofpress |

Customize the list in `scripts/find_issues.py` → `ORGANIZATIONS`

---

## 🔒 Security Notes

- `GH_TOKEN` is stored as a GitHub secret — never committed to code
- The auto-comment workflow **only triggers when you** (`kiranShamsHere`) comment
- Nobody else can trigger auto-comments from this repo

---

## 📈 Expected Results

| Timeframe | Goal |
|-----------|------|
| Day 1 | First digest with 30-40 issues, pick your favorites |
| Week 1 | 3-5 assignment requests sent, 1-2 accepted |
| Month 1 | Multiple merged PRs across different orgs |
| Month 3 | Strong open source portfolio, recruiters notice |

---

## 🤝 Contributing

Ideas for improvements:
- Filter out repos that block external comments
- Add difficulty scoring
- Add language/tech stack filtering
- Build a web dashboard

PRs welcome!

---

*"Dream it. Code it. Ship it." — Kiran Shams*