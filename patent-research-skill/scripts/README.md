# scripts/ — the skill package's local execution scripts

> **In one sentence**: they wrap patentkit's validation / gate / report capabilities into **repeatable, LLM-client-friendly** commands.
> They only "locate the workspace + call the API + present results + normalize exit codes" and **copy no rules**.

## Why this layer exists

| Scenario | Running `patentkit` directly | Running `scripts/` |
|---|---|---|
| Chinese Windows terminal | Output of ✅/⚠️ may crash with `UnicodeEncodeError` | Scripts lock UTF-8 at startup |
| Client missing the package / not in the right cwd | A screenful of traceback; or a misleading "glossary does not exist" | exit 3 with the install command; exit 2 with three fixes |
| Machine-parsed output | Human text mixed with JSON | With `--json`, stdout contains **exactly one JSON** |
| Exit codes | gates failure returns 2, colliding with workspace errors | Unified: 1 = business failure, 2 = workspace problem |

**This is a thin wrapper, not a replacement.** The single implementation of rules and thresholds remains in `patentkit/`:

| Capability | Single implementation site |
|---|---|
| Programmatic entry point (every command here calls only this) | `patentkit/api.py` |
| Consistency validation V001-V030 | `patentkit/validate.py` |
| Acceptance gates G-S-01..05 | `patentkit/gates.py` |
| Shared assessment eligibility, original-text support and human confirmation | `patentkit/assessment.py` |
| Comparison run skeleton | `patentkit/report.py` |

## Dependencies

| Dependency | Requirement | How to check / install |
|---|---|---|
| Python | ≥ 3.11 | `python --version`; below this version the scripts exit 3 |
| patentkit | ≥0.2.0, assessment protocol 1 (older kernels exit 3) | `pip install -e ".[dev]"`; or `pip install patentkit` |
| Self-check | workspace resolvable, dependencies complete | `python -m patentkit doctor` |

> When patentkit is not installed, the scripts do **not** throw a traceback; they print the install instructions and exit 3.

## Quick start (PowerShell)

```powershell
# Run from the repo root. Workspace resolution order: --root → PATENTKIT_WORKSPACE → search upward for workspace.yml
python patent-research-skill/scripts/status.py

# Machine-readable (recommended for LLM clients)
python patent-research-skill/scripts/status.py --json

# Specify the workspace from any directory
python patent-research-skill/scripts/gates.py --root <patent-workspace>

# CI mode: check data consistency and all five gates together
python patent-research-skill/scripts/check.py --json
```

## Commands at a glance

| Script | What it does | API called | Exit codes |
|---|---|---|---|
| `status.py` | Target / one-line summary of the five gates / validation / candidate distribution / next-step hints | `api.status` | 0 data readable (whether gates PASS does not affect this command) |
| `validate.py` | V001-V028 consistency validation; with `--strict`, warnings also count as failures | `api.validate` | 0 pass / 1 blocking findings |
| `gates.py` | Five gates × three-column summary; **PASS is recognized only on the verified column** | `api.gates` | 0 all five PASS / 1 some gate not passed (including N/A) |
| `report.py` | Generate the comparison run skeleton under `04_comparative_analysis/runs/` | `api.report` | 0 success / 1 generation or write failure |
| `check.py` | `validate --strict` + `gates` (pre-commit / CI entry) | the two above | 0 all pass / 1 any failure |
| `_env.py` | Shared layer: UTF-8, dependency checks, workspace resolution, JSON output | — (imported by the five commands above) | — |

All five commands support `--root PATH` and `--json`.

### Common arguments

| Argument | Effect |
|---|---|
| `--root PATH` | Explicitly set the workspace root; a relative path is resolved against the **current directory** |
| `--json` | stdout contains only one JSON document (`ensure_ascii=False, indent=2`); human hints go to stderr only |

### `gates.py`'s `--target` (multi-target workspaces)

By default the gates only count candidates and logs of the glossary's `active_target`. Multi-target workspaces must
specify it explicitly; otherwise you see the gates of "the currently active target", not the one you meant:

```powershell
python patent-research-skill/scripts/gates.py --target TGT-0002
```

Where does the target ID come from: run `status.py` first to see `active_target`, or check `targets` in `00_methodology/glossary.yml`.

### Two details of report.py

```powershell
# Writing to disk: a relative --out path is resolved against the **workspace root**, not the current directory
python patent-research-skill/scripts/report.py --target TGT-0002 `
    --out 04_comparative_analysis/runs/2026-01-01_TGT-0002.md

# Preview only, no write: omit --out and the skeleton goes straight to stdout
python patent-research-skill/scripts/report.py --target TGT-0002
```

- `--target` must match an entry in `targets` of `00_methodology/glossary.yml`; otherwise the axes in the skeleton are empty (no error is raised, so **confirm the current target with `status.py` first**).
- `--out` has **no default**: writing to disk by default would pollute workspace data before the user has thought it through — better to type one extra argument.
- §6 of the skeleton asks you to fill in `capture_mode`: only `live` can qualify as verified; `retrospective` / `memory` can only qualify as asserted.

## Exit codes

| Code | Meaning | Typical scenario |
|---|---|---|
| 0 | Success | The command's own determination passed |
| 1 | Business failure | Validation has errors (with strict also warnings) / not all gates PASS / report cannot be written |
| 2 | Workspace problem | Workspace not found, wrong `--root`, wrong `PATENTKIT_WORKSPACE`, corrupted workspace data; argparse usage errors are also 2 |
| 3 | Missing dependency | Python < 3.11, or patentkit / its dependencies not installed |
| 130 | Interrupted by Ctrl+C | Not a business code; lets callers distinguish "interrupted" from "failed" |

> **Differences from the native `patentkit` CLI (important)**
>
> * `python -m patentkit gates` returns **2** when not all gates pass; `gates.py` here returns **1**.
> * `python -m patentkit check` returns **2** when gates do not pass; `check.py` here returns **1**.
>
> Reason: the skill package uniformly defines **2 as workspace problem only**. Otherwise clients misread
> "gates did not pass" as "the workspace is broken". To distinguish failure causes, look at `validate.ok` and
> `gates.all_pass` in the `--json` result.

## Workspace resolution (three fixes when it fails)

Fixed order:

1. `--root PATH` — explicit, per invocation;
2. environment variable `PATENTKIT_WORKSPACE` — set once, then usable from any directory;
3. search upward from the current directory for `workspace.yml` — just run it from the repo root or any subdirectory.

```powershell
# 1) cd into the workspace root (containing workspace.yml)
cd <workspace>
python patent-research-skill/scripts/status.py

# 2) Specify it per invocation
python patent-research-skill/scripts/status.py --root <workspace>

# 3) Set the environment variable (current session)
$env:PATENTKIT_WORKSPACE = "<workspace>"
python patent-research-skill/scripts/status.py
```

> Failure to locate the workspace **does not** silently fall back to the current directory — that would disguise
> "you are not in a workspace" as "the glossary does not exist", a pit this repository has fallen into before.
> Now it uniformly exits 2 with the three fixes.

## Windows / UTF-8 notes (must read)

* At startup the scripts lock stdout/stderr to **UTF-8** (`_env.configure_stdio()`), therefore:
  * there is no need to run `chcp 65001` first, nor to set `PYTHONIOENCODING`;
  * `✅ / ❌ / ⚠️` in the output will not crash the command.
* **The parent process must decode captured output as UTF-8**. In Python:

  ```python
  subprocess.run([...], capture_output=True, text=True, encoding="utf-8")
  ```

  Decoding with the system default code page (cp936) produces mojibake — that is not a script problem.
* All files (scripts / this document) are UTF-8 without BOM.

## `--json` output contract

* Success: stdout contains exactly one JSON object with `ok: true` and a `command` field; other fields come from the corresponding `api.*` return value.
* Failure (exit 1 / 2 / 3): if `--json` was given, stdout contains:
  `{"ok": false, "code": <exit code>, "error": "...", "hints": ["..."]}`.
* Without `--json`, human hints (`❌ …` and the fixes) go to **stderr**; stdout is not mixed with hints.
* `argparse` usage errors (e.g. a missing `--target`) follow argparse's default behavior: stderr + exit 2, no JSON guaranteed — this is intentional, since usage errors should be avoided before invoking.

## Calling advice for LLM clients

1. **Start with `status.py --json` to get the global picture** (target / gates / validation / candidates / hints); do not call five commands back to back.
2. Run `check.py --json` only when you need a machine verdict; only exit code 0 means "the current data passes".
3. The only basis for determination is `gates[].values.verified`; `attested` / `asserted` are historical record and **do not constitute a basis for PASS**.
4. When the client cannot execute code, every conclusion must be marked "⚠️ Unverified by tool checks" and must not be disguised as verified.
5. Keep source grades separate from judgments: supported AI scoring is allowed for G-S-02; G-S-03 requires actual human confirmation of explicit IDs/fingerprints. AI conflicts remain proposals. See ../references/07-assessment-protocol.md.
6. `report.py` **really writes to disk**; first confirm the path in the `out` field of the `--json` result, and do not try it casually in a real workspace.

## What it does not do

* **Does not copy rules**: validation rules, gate thresholds, and the three-column criteria all live in `patentkit/`; change the criteria in the source — this directory contains zero rules.
* **Does not write workspace data**: the only write operation is `report.py --out`, and the path must be given explicitly by the caller.
* **Does not go online**: all commands read local files only.
* **Does not git add / commit**.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| exit 3 | patentkit not installed / Python too old | Install as prompted; then `python -m patentkit doctor` |
| exit 2 + three fixes | Workspace not located | Follow the hints: cd / `--root` / set `PATENTKIT_WORKSPACE` |
| exit 2 + "not a workspace" | `--root` points to an ordinary directory | Confirm that directory contains `workspace.yml` |
| exit 1 + validation failure | Data inconsistency | Look at the error's V0xx rule code and fix the data first |
| exit 1 + gates not passed | Insufficient searching / review | Add searches or relevance reviews — **do not loosen the criteria** |
| JSON parsing fails | `--json` not given, or decoding is not UTF-8 | Add `--json`; decode as UTF-8 in the parent process |
| Reports "missing dependency module X" | patentkit installed but dependencies incomplete | `pip install -e ".[dev]"` |
