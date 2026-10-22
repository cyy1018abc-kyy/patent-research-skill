# scripts/ — local execution layer for the skill

> Thin wrappers around the `patentkit` kernel: locate the workspace, call the API,
> present the result, and converge exit codes. They do **not** duplicate any rules.

## Commands

| Script | Purpose | Typical usage |
|---|---|---|
| `status.py` | one-shot status: target, gates, validation, candidates, next hints | `python scripts/status.py --json` |
| `validate.py` | consistency validation V001–V028 | `python scripts/validate.py --strict` |
| `gates.py` | G-S-01..05 acceptance gates (three evidence levels) | `python scripts/gates.py --json` |
| `report.py` | generate a report skeleton | `python scripts/report.py --target TGT-0002` |
| `check.py` | CI entry: validate + gates | `python scripts/check.py` |

All scripts accept `--root <workspace>` and default to locating `workspace.yml` from
the current directory upward (or `PATENTKIT_WORKSPACE`). The skill directory itself is
**not** the workspace.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success / all checks passed |
| 1 | business failure (validation errors or gates not PASS) |
| 2 | workspace/structure problem (no `workspace.yml`, invalid package layout) |
| 3 | dependency problem (`patentkit` not installed, Python < 3.11) |

`--json` prints a single JSON object on stdout and keeps stdout free of logs.
Errors go to stderr.

## Requirements

- Python >= 3.11
- `patentkit` >= 0.1.1 (`pip install patentkit-*.whl`)
- A valid workspace (start with the bundled synthetic `samples/sample-workspace/`)

## Examples

```powershell
cd <workspace>
python <skill>/scripts/status.py --json
python <skill>/scripts/validate.py --strict
python <skill>/scripts/gates.py --json
```

```powershell
# from anywhere, explicit workspace
python <skill>/scripts/status.py --root "<workspace>"
```

## Notes

- The scripts are read-only by default; `--write`-style operations are explicit.
- Gate PASS is computed only from the `verified` column, never from `asserted`.
- The skill's runtime documentation and script output remain in Chinese because the
  product targets Chinese patent practice.
