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

**deathbed** analyses every tracked source file in a git repository and gives it a **health score** based on six real, local metrics — no external API calls, no secrets needed.  It then surfaces the files most likely to cause you pain, explains *why* they are dying, and tells you exactly what to do first.

---

## Why?

Every codebase accumulates rot.  Files that nobody owns.  Files too complex to understand.  Files last touched three years ago by someone who left.  These files never show up in sprint planning, but they quietly cause the most bugs, the slowest onboarding, and the worst incidents.

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
pip install -e .
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

# Combine flags
deathbed --path ~/projects/myapp --top 10 --format json
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--path`, `-p` | `.` | Path to the git repository |
| `--top`, `-t` | `50` | Show only the N worst files (0 = all) |
| `--min-score` | — | Only show files with a health score below this value |
| `--format`, `-f` | `rich` | Output format: `rich` or `json` |
| `--version`, `-V` | — | Show version and exit |

---

## What it looks like

When you run `deathbed` you get:

![deathbed demo](demo.gif)

---

## Metrics explained

Each file receives a **composite health score from 0–100** (higher is healthier), built from six weighted sub-scores:

| # | Metric | Weight | What it measures |
|---|--------|--------|-----------------|
| 1 | **Size** | 15% | Lines of code — penalises files > 300 / 600 / 1000 lines |
| 2 | **Age** | 20% | Days since any commit touched this file — flags abandoned code |
| 3 | **Churn** | 20% | Number of commits to this file — instability signal |
| 4 | **Complexity** | 20% | Radon cyclomatic complexity average — Python files only; N/A otherwise |
| 5 | **Authors** | 15% | Unique git authors — many authors = diffused ownership |
| 6 | **Test coverage** | 10% | Whether a corresponding test file exists anywhere in the repo |

### Health thresholds

| Score | Status | Meaning |
|-------|--------|---------|
| 86–100 | ✅ HEALTHY | All good |
| 66–85 | 🌡 FAIR | Minor issues |
| 41–65 | ⚠️ WARNING | Needs attention soon |
| 0–40 | 💀 CRITICAL | Actively dangerous |

### Diagnoses

deathbed automatically picks the most meaningful single-phrase diagnosis:

| Diagnosis | What it means |
|-----------|--------------|
| `complexity graveyard` | Cyclomatic complexity is extremely high |
| `legacy ghost` | Not touched in years — likely orphaned |
| `too many cooks` | Many authors, nobody owns it |
| `churn monster` | Modified constantly — unstable abstraction |
| `growing out of control` | Large and getting larger |
| `nobody's watching this` | Old code with no test coverage |
| `abandoned and complex` | Old *and* hard to understand |
| `healthy` | Nothing to worry about |

---

## JSON output

`--format json` returns a machine-readable object useful for CI gates:

```json
{
  "version": "1.0.0",
  "repo": "/path/to/repo",
  "total": 3,
  "files": [
    {
      "file": "src/legacy/monster.py",
      "health_score": 22,
      "status": "CRITICAL",
      "diagnosis": "complexity graveyard",
      "lines": 1284,
      "days_since_commit": 847,
      "commit_count": 134,
      "author_count": 9,
      "avg_complexity": 18.3,
      "has_test_file": false,
      "scores": {
        "size": 0, "age": 5, "churn": 15,
        "complexity": 2, "authors": 20, "test": 20
      }
    }
  ]
}
```

---

## Supported file types

`.py` `.js` `.ts` `.jsx` `.tsx` `.go` `.rs` `.rb` `.java` `.cpp` `.c` `.cs` `.php` `.swift` `.kt`

Automatically skipped: `node_modules`, `venv`, `dist`, `build`, `.git`, binary files, lock files, and everything matched by `.gitignore`.

---

## Contributing

1. Fork the repo
2. Create a branch: `git checkout -b feat/my-idea`
3. Make your changes (run `deathbed` against itself to test!)
4. Open a pull request

Bug reports and feature ideas welcome via [Issues](https://github.com/yourusername/deathbed/issues).

---

<p align="center">
  Made with 💀 and <a href="https://github.com/Textualize/rich">Rich</a>
</p>
