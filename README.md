  ```
                       ██████╗ ███████╗ █████╗ ████████╗██╗  ██╗██████╗ ███████╗██████╗
                       ██╔══██╗██╔════╝██╔══██╗╚══██╔══╝██║  ██║██╔══██╗██╔════╝██╔══██╗
                       ██║  ██║█████╗  ███████║   ██║   ███████║██████╔╝█████╗  ██║  ██║
                       ██║  ██║██╔══╝  ██╔══██║   ██║   ██╔══██║██╔══██╗██╔══╝  ██║  ██║
                       ██████╔╝███████╗██║  ██║   ██║   ██║  ██║██████╔╝███████╗██████╔╝
                       ╚═════╝ ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═════╝ ╚══════╝╚═════╝
```

<p align="center">
  <em>every codebase has files that are dying.  find them.</em>
</p>

<p align="center">
  <img alt="Python 3.9+" src="https://img.shields.io/badge/python-3.9%2B-crimson?style=flat-square">
  <img alt="License MIT" src="https://img.shields.io/badge/license-MIT-crimson?style=flat-square">
  <img alt="Rich" src="https://img.shields.io/badge/powered%20by-Rich-crimson?style=flat-square">
  <img alt="PyPI" src="https://img.shields.io/pypi/v/deathbed?style=flat-square&color=crimson">
</p>

---

**deathbed** analyses every tracked source file in a git repository and gives it a **health score** based on nine real, local metrics — no external API calls, no secrets needed.  It surfaces the files most likely to cause you pain, explains *why* they are dying, and tells you exactly what to do first.

**v2.0.0** adds multi-repo org scanning, an AI-free refactor planner, and GitHub Actions integration.

---

## Why?

Every codebase accumulates rot.  Files that nobody owns.  Files too complex to understand.  Files last touched three years ago by someone who left.  Files importing `pickle` in a web handler.  These files never show up in sprint planning, but they quietly cause the most bugs, the slowest onboarding, and the worst incidents.

deathbed makes the invisible visible.

---

## Install

```bash
pip install deathbed
```

Or, to hack on it:

```bash
git clone https://github.com/NikoloziKhachiashvili/deathbed
cd deathbed
pip install -e ".[dev]"
```

---

## Usage

```bash
# Analyse the current git repo
deathbed

# Analyse a different repo
deathbed --path /path/to/repo

# Show only the 20 worst files
deathbed --top 20

# Show only WARNING and CRITICAL files (score < 65)
deathbed --min-score 65

# Output JSON for CI pipelines / scripting
deathbed --format json

# Output a Markdown table (for GitHub comments etc.)
deathbed --format markdown

# Live auto-refreshing dashboard (re-runs every 30s)
deathbed --watch

# Compare health scores between HEAD and HEAD~1
deathbed --diff HEAD~1

# Compare HEAD against any ref
deathbed --diff main

# Export a self-contained HTML report
deathbed --export html

# CI mode — exit 1 if any CRITICAL files are found
deathbed --ci

# Combine flags
deathbed --path ~/projects/myapp --top 10 --format json
deathbed --min-score 70 --ci

# PR mode — only files changed since main
deathbed --since main

# Show last author in the table and Most Wanted panel
deathbed --blame

# Team leaderboard by last-commit author
deathbed --leaderboard

# Scan an entire org directory of git repos
deathbed --org /path/to/projects

# Drill into one repo from an org scan
deathbed --org /path/to/projects --repo myapp

# Generate a prioritised refactor plan (Sprint 1/2/3 roadmap)
deathbed --plan

# Write a GitHub Actions workflow to .github/workflows/deathbed.yml
deathbed --init-ci

# Print a shields.io health badge for your README
deathbed --badge
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--path`, `-p` | `.` | Path to the git repository |
| `--top`, `-t` | `50` | Show only the N worst files (0 = all) |
| `--min-score` | — | Only show files with a health score below this value |
| `--format`, `-f` | `rich` | Output format: `rich`, `json`, or `markdown` |
| `--watch`, `-w` | — | Live auto-refreshing dashboard (30s interval) |
| `--diff REF` | — | Compare health scores between HEAD and REF |
| `--export html` | — | Export a self-contained HTML report to `deathbed-report.html` |
| `--ci` | — | Exit code 1 if any CRITICAL files found (for CI pipelines) |
| `--since REF` | — | PR mode — restrict to files changed since REF (e.g. `main`) |
| `--blame` | — | Show last-author column in table and blame info in Most Wanted |
| `--leaderboard` | — | Team view: authors ranked by files needing support |
| `--org PATH` | — | Scan a directory of git repos and show an org-wide health table |
| `--repo NAME` | — | With `--org`: drill into a single repo by name |
| `--plan` | — | Generate a prioritised Sprint 1/2/3 refactor roadmap |
| `--init-ci` | — | Write a GitHub Actions workflow to `.github/workflows/deathbed.yml` |
| `--badge` | — | Print a shields.io Markdown health badge for your README |
| `--version`, `-V` | — | Show version and exit |

---

## What it looks like

When you run `deathbed` you get:

![deathbed demo](demo.gif)

---

## Metrics explained

Each file receives a **composite health score from 0–100** (higher is healthier), built from nine weighted sub-scores:

| # | Metric | Weight | What it measures |
|---|--------|--------|-----------------|
| 1 | **Size** | 11.7% | Lines of code — penalises files > 300 / 600 / 1000 lines |
| 2 | **Age** | 11.7% | Days since any commit touched this file — flags abandoned code |
| 3 | **Churn** | 8.1% | Total number of commits — instability signal |
| 4 | **Complexity** | 16.2% | Radon cyclomatic complexity average — Python only; N/A otherwise |
| 5 | **Authors** | 10.8% | Unique git authors — many authors = diffused ownership |
| 6 | **Test coverage** | 8.1% | Whether a corresponding test file exists and has real assertions |
| 7 | **Recent churn** | 14.4% | Commits in the last 90 days — hotspot detection |
| 8 | **Dead code** | 9.0% | Unused functions/classes/variables detected by vulture (Python only) |
| 9 | **Coupling** | 10.0% | How many other files import this file — high coupling = fragile hub |

### Health thresholds

| Score | Status | Meaning |
|-------|--------|---------|
| 86–100 | ✅ HEALTHY | All good |
| 66–85 | 🌡 FAIR | Minor issues |
| 41–65 | ⚠️ WARNING | Needs attention soon |
| 0–40 | 💀 CRITICAL | Actively dangerous |

### Diagnoses

deathbed automatically picks the most meaningful diagnosis:

| Diagnosis | What it means |
|-----------|--------------|
| `security smell` | File imports dangerous patterns (pickle, eval, exec, os.system, subprocess shell=True) |
| `god file` | High coupling (5+ importers) AND already complex AND large — the worst kind of hub |
| `clone risk` | File is >40% similar to another file — likely a copy-paste |
| `test theatre` | Has a test file but the test contains zero assertions — false safety net |
| `dead code cemetery` | High vulture score — lots of unused symbols |
| `haunted` | 5+ authors AND high complexity AND still churning — too many cooks, no one understands it |
| `ownership void` | Abandoned for 6+ months and only ever touched by 1 author |
| `complexity graveyard` | Cyclomatic complexity is extremely high |
| `legacy ghost` | Not touched in years — likely orphaned |
| `too many cooks` | Many authors, nobody owns it |
| `churn monster` | Modified constantly — unstable abstraction |
| `growing out of control` | Large and getting larger |
| `nobody's watching this` | Old code with no test coverage |
| `abandoned and complex` | Old *and* hard to understand |
| `healthy` | Nothing to worry about |

Any diagnosis can gain the ` 🔥 heating up` suffix when recent commit activity has spiked 2× over the prior 90-day window.

---

## Trend arrows in the table

The **RECENT** column shows trend arrows alongside the 90-day commit count:

| Arrow | Meaning |
|-------|---------|
| ▲ | Recent churn is 1.5× higher than the prior 90 days — hotspot forming |
| ▼ | Activity has dropped significantly — cooling down |
| ━ | Stable activity or insufficient data |

---

## SECURITY ALERTS panel

If any files contain dangerous import or call patterns, a dedicated red **SECURITY ALERTS** panel appears below the main report, listing every affected file and the specific patterns detected.

---

## Coupling

The **COUP** column in the main table shows how many other files import each file.  Files with 5+ importers are flagged as coupling hotspots and counted in the SCAN COMPLETE bar.

A dedicated **MOST COUPLED** panel lists the top 3 most-imported files and shows which files depend on them.  When a file is both heavily coupled *and* complex and large, it receives the `god file` diagnosis.

---

## Live watch mode

```bash
deathbed --watch
```

Re-scans the repository every 30 seconds, clears the screen, and reprints the full report.  Press **Ctrl+C** to stop.

---

## Diff mode

```bash
deathbed --diff HEAD~1
deathbed --diff main
```

Compares health scores between the current state (HEAD) and any historical git ref.  Shows ▲ improved / ▼ worsened / ━ unchanged with exact deltas.

---

## HTML export

```bash
deathbed --export html
```

Writes a fully self-contained **`deathbed-report.html`** to the current directory.  The report mirrors the terminal UI with:
- Dark red/green colour scheme
- Sortable table (click any column header)
- Score gauges per file
- Most Wanted breakdown
- Quick Wins list
- Security Alerts (if any)

No external dependencies — one file, works offline.

---

## Multi-repo org scanning

```bash
# Scan every git repo in a directory
deathbed --org /path/to/projects

# Drill into one specific repo
deathbed --org /path/to/projects --repo myapp
```

Scans every immediate subdirectory that is a git repository and displays an org-wide health table sorted worst-first:

| Column | Meaning |
|--------|---------|
| GRADE | Letter grade A–F for the repo |
| REPO | Repository directory name |
| SCORE | Overall repo health score (0–100) |
| CRITICAL | Number of CRITICAL files |
| WARNING | Number of WARNING files |
| FILES | Total files scanned |
| WORST FILE | The single most unhealthy file |
| WORST SCORE | Its health score |

A combined **ORG SCORE** is shown at the bottom — the average across all successfully scanned repos.

---

## Refactor planner

```bash
deathbed --plan

# Export the plan as Markdown
deathbed --plan --format markdown
```

Generates a prioritised **Sprint 1 / 2 / 3 roadmap** from the current scan results.  Each item includes:
- The file and its diagnosis
- A concrete, per-diagnosis action (e.g. "Split into smaller modules", "Replace pickle with json", "Add assertions to test")
- Effort estimate: **Small**, **Medium**, or **Large**
- Current health score

Sprint 1 = CRITICAL files with Small/Medium effort (highest ROI).
Sprint 2 = remaining CRITICAL + WARNING files.
Sprint 3 = lower-priority improvements.

---

## GitHub Actions integration

### Auto-setup

```bash
deathbed --init-ci
```

Writes a ready-to-use workflow to `.github/workflows/deathbed.yml` that runs `deathbed --ci` on every push and pull request.  Commit and push the file to activate it.

### Health badge

```bash
deathbed --badge
```

Prints a shields.io Markdown badge reflecting the current repo score.  Paste it into your README:

```markdown
![deathbed score](https://img.shields.io/badge/deathbed-82%20B-4caf50?style=flat-square&logo=data:...)
```

---

## CI integration

```bash
# In .github/workflows/ci.yml or similar:
deathbed --ci --min-score 50
```

Exits with **code 1** if any files are CRITICAL (score ≤ 40), printing a list of offending files to stderr.  Exits 0 otherwise.

---

## Trend history (▲▼━ in the TREND column)

deathbed stores a rolling history of up to 10 scans per repo in `~/.deathbed/history.json`.  On subsequent runs the **TREND** column appears in the table, showing each file's score delta vs the previous scan:

| Symbol | Meaning |
|--------|---------|
| `▲ +N` | Score improved by N points since last scan |
| `▼ -N` | Score worsened by N points since last scan |
| `━  0` | No change |

The **Most Wanted** panel also shows a 5-character sparkline (▁▂▃▄▅▆▇█) built from the file's score history.

The **SCAN COMPLETE** panel shows the repo's overall weighted score (0–100) with a letter grade (A–F) and delta vs the previous scan.

---

## PR mode

```bash
deathbed --since main
deathbed --since HEAD~5
```

Restricts the scan to files that have changed between `<REF>` and `HEAD`.  The SCAN COMPLETE panel notes "PR mode — N files changed since <ref>".  Ideal for per-PR health gates in code review.

---

## Blame mode

```bash
deathbed --blame
```

Adds a **LAST AUTHOR** column to the table showing who last committed to each file.  The Most Wanted panel also shows the last commit author and subject line.

---

## Team leaderboard

```bash
deathbed --leaderboard
```

Runs a full blame-enriched scan and groups results by last-commit author:

| Column | Meaning |
|--------|---------|
| AUTHOR | Git author name |
| FILES | Number of files owned (last commit) |
| AVG SCORE | Average health score across owned files |
| CRITICAL | Files in CRITICAL state |
| WARNING | Files in WARNING state |
| GRADE | Letter grade A–F |

Sorted by most at-risk first.  Framed as *who needs support*, not a blame ranking.

---

## Ignore file (.deathbedignore)

Create a `.deathbedignore` file in your repo root using the same gitignore syntax to permanently exclude files from analysis:

```
# .deathbedignore
vendor/**
legacy/old_migration.py
generated/**/*.py
```

The SCAN COMPLETE panel reports how many files were ignored.

---

## JSON output

`--format json` returns a machine-readable object:

```json
{
  "version": "2.0.0",
  "repo": "/path/to/repo",
  "total": 3,
  "files": [
    {
      "file": "src/legacy/monster.py",
      "health_score": 22,
      "status": "CRITICAL",
      "diagnosis": "god file",
      "lines": 1284,
      "days_since_commit": 847,
      "commit_count": 134,
      "author_count": 9,
      "avg_complexity": 18.3,
      "has_test_file": false,
      "test_has_assertions": false,
      "dead_code_count": 12,
      "has_security_smell": true,
      "security_smells": ["imports pickle", "calls eval()"],
      "clone_similarity": 0.0,
      "clone_of": "",
      "coupling_count": 7,
      "importers": ["src/api/handler.py", "src/utils/loader.py"],
      "scores": {
        "size": 0, "age": 5, "churn": 15,
        "complexity": 2, "authors": 20, "test": 10,
        "recent_churn": 40, "dead_code": 20, "coupling": 40
      }
    }
  ]
}
```

---

## Markdown output

```bash
deathbed --format markdown
```

Emits a GitHub-Flavored Markdown table suitable for pasting into PR comments or issue trackers.

---

## Supported file types

`.py` `.js` `.ts` `.jsx` `.tsx` `.go` `.rs` `.rb` `.java` `.cpp` `.c` `.cs` `.php` `.swift` `.kt`

Automatically skipped: `node_modules`, `venv`, `dist`, `build`, `.git`, binary files, lock files, and everything matched by `.gitignore` or `.deathbedignore`.

---

## Contributing

1. Fork the repo
2. Create a branch: `git checkout -b feat/my-idea`
3. Make your changes and run tests: `pytest`
4. Run deathbed against itself: `deathbed`
5. Open a pull request

Bug reports and feature ideas welcome via [Issues](https://github.com/NikoloziKhachiashvili/deathbed/issues).

---

## License

MIT License — Copyright (c) 2026 Nikolozi Khachiashvili

---

<p align="center">
  Made with 💀 and <a href="https://github.com/Textualize/rich">Rich</a>
</p>
