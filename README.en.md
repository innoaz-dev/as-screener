# AS Screener

**A local tool that scans third-party agent skills (SKILL.md), strips everything executable, rewrites only the intent, and installs the result after automatic checks and your approval.**

[한국어](README.md)

Skills you download for Claude Code or Codex can hide instructions such as "ignore previous instructions", "don't tell the user", or "quietly send the SSH key". AS Screener finds them before installation and, instead of installing the original text, installs a **clean rewrite that keeps only the intent**.

## Why

NVIDIA's [SkillSpector](https://github.com/NVIDIA/skillspector) is a good skill scanner, but its static scan (the fast, LLM-free first pass) is English-centric. In our tests, the same malicious instructions written in Korean, Chinese, Japanese and Spanish all passed SkillSpector v2.12.0's static scan with a **score of 0 (safe)**. AS Screener closes that gap with YARA rules for Korean, Chinese and Japanese.

## What it does

1. **Scan** — SkillSpector static scan + Korean/Chinese/Japanese YARA rules. Free, a few seconds. Optional LLM deep scan via Claude Code
2. **Strip executables** — scripts, hooks, `.mcp.json` and config files are dropped; only text instructions (SKILL.md, references) are kept
3. **Rewrite** — a tool-less Claude reads the original strictly as data and writes the intent from scratch (hidden instructions are removed)
4. **Six automatic checks** — format, newly introduced risks, copy ratio, static rescan, LLM rescan, and an intent-preservation review by a separate Claude. Failures trigger an automatic retry (up to 2)
5. **Human approval** — nothing is saved until you approve. Source, file fingerprints (SHA-256) and the original license are recorded
6. **Install & manage** — install/uninstall into Claude Code (`~/.claude/skills`) and Codex (`~/.codex/skills`), with tamper detection

Everything happens on a single paste form: paste a GitHub URL, a folder path or the SKILL.md text and press the button. (The UI is in Korean.)

## Requirements

| Item | Purpose | Required |
|---|---|---|
| Windows 10/11 | Developed and tested here (macOS/Linux not yet tested) | ✓ |
| [uv](https://docs.astral.sh/uv/) | Runs Python 3.12 | ✓ |
| [SkillSpector](https://github.com/NVIDIA/skillspector) | First-pass scan engine (tested with v2.12.0) | ✓ |
| [Claude Code](https://docs.claude.com/en/docs/claude-code/overview), installed and logged in | LLM deep scan and rewriting. **Uses your own account's usage** | For rewriting |

AS Screener itself uses only the Python standard library.

## Install and run

```powershell
# 1. Install SkillSpector (lower concurrency if your PC slows down)
$env:UV_CONCURRENT_DOWNLOADS=2; $env:UV_CONCURRENT_BUILDS=2
uv tool install --python 3.12 git+https://github.com/NVIDIA/skillspector.git

# 2. Get this repository
git clone https://github.com/innoaz-dev/as-screener.git
cd as-screener

# 3. Run (same as double-clicking AS스크리너.bat)
uv run --python 3.12 as_screener.py
```

Your browser opens `http://127.0.0.1:8765`. The form is reachable only from your own machine.

## Tests

```powershell
uv run --python 3.12 tests\run_regression.py      # same as 테스트실행.bat
```

14 fixture checks (expected verdict, rules and line numbers for 13 test skills, plus a self-scan of the rule files), 12 unit tests for the rewriter, line-number correction and timing log, and 9 installer tests — all 35 must pass. Each run appends its timing to `tests/timing_log.csv` (not committed).

> ⚠️ The `test-skills/*-injection*` folders and `eval/` contain **intentionally malicious text for detection tests**. Never install them or put them into a prompt.

## Rule results

The rules have two tiers:
- **Block** (HIGH/CRITICAL) matches only actual commands. Negations ("don't send…"), quotations ("the phrase 'ignore…'") and descriptions ("attackers make the model…") are not matched.
- **Caution** (MEDIUM) flags phrases that are suspicious but can be legitimate, such as "follow only this document" or "gather the .env files". Review them yourself.

| Language | Rules (block + caution) | Unseen attack sentences | False positives on public skills (block tier) |
|---|---|---|---|
| Korean `rules/ko` | 6 + 3 | 15 of 60 (25%) | 53 public repos, 3,752 Korean-heavy files, 0 |
| Chinese (Simplified) `rules/zh` | 6 + 2 | 18 of 60 (30%) | 20 public repos, 4,060 Chinese-heavy files, 0 |
| Japanese `rules/ja` | 6 + 3 | 16 of 60 (26%) | 40 public repos, 1,287 Japanese-heavy files, 0 |

- The six categories: instruction override · concealment from the user · stealth execution · jailbreak phrases · credential access · credential exfiltration
- **Unseen attack sentences** come from a held-out set (`eval/heldout.jsonl`), written by an author who did not know the rules and never used while tuning them. The previous rules (v0.4/v0.1) caught only 1–8% of the same set.
- Of the 90 tricky benign sentences in that set (negations, security docs, etc.), 5 were flagged, 3 of them at the block tier.
- Across all 16,308 public skill files, 7 caution-tier hits. On 38,850 files of English attack and benchmark data, the Korean/Chinese/Japanese rules matched English text 0 times.
- Scorecard: `uv run --python 3.12 --with yara-python tools\measure_recall.py heldout` (details in [eval/README.md](eval/README.md), Korean)
- The rule files are generated by `tools/rulegen/`. Korean/Chinese/Japanese characters are written as `\xNN` bytes so the rule files don't match themselves.

## Limitations

- **Static rules catch only about a quarter of unseen attacks.** Indirect phrasing, concealment and jailbreak phrases slip through most often. Treat the static rules as a fast first filter and turn on the LLM deep scan for skills you haven't seen before; in our tests the LLM mode caught the Korean, Chinese, Japanese and Spanish test skills.
- The evaluation sentences were also written by an AI (Claude), so they may differ from what real attackers write.
- No Spanish or Traditional Chinese rules yet.
- Tested on Windows only.
- A rewrite or translation can still be a derivative work of the original. AS Screener saves the original license as `LICENSE.original` and warns "personal use only" when no license is found. Check the original license before redistributing a rewrite.

## Security design

- The scanned skill's code is **never executed** (read only).
- The rewriting Claude runs with no tools, no MCP servers and no settings files; the original is passed only as data.
- Output is limited to `SKILL.md` and `references/*.md` (path traversal is blocked).
- The local web form listens on `127.0.0.1` only and uses a fresh one-time token per run to reject requests from other websites.
- The installer only overwrites or removes skills it installed itself. A skill with the same name that you wrote is never touched.

## License and attribution

- [Apache License 2.0](LICENSE)
- SkillSpector (NVIDIA, Apache-2.0) is installed separately and only invoked; no SkillSpector code is included in this repository.
- This is an independent project, not affiliated with NVIDIA or Anthropic. Claude is a trademark of Anthropic.
- Made by Innoaz (이노아즈)

Please report security issues (e.g. ways to bypass detection) as described in [SECURITY.md](SECURITY.md), not in public issues.
