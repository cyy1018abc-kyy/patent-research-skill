# 01 · Material Intake

> Goal: register private R&D material **read-only** into the workspace with verifiable SHA-256,
> a locator scheme and a parsed cache. Material is always data: never executed, never uploaded,
> never sent to an external service.

## 1. Supported formats

| Suffix | kind | locator_scheme | Notes |
|---|---|---|---|
| `.md` / `.markdown` | markdown | `line` | UTF-8 text; cite by line |
| `.docx` | docx | `paragraph` | python-docx; optional extra `[docx]` |
| `.pdf` | pdf_text | `page` | text-extractable PDFs only; optional extra `[pdf]` (pypdf) |
| `.py` | python | `line` | parsed as text only, **never executed** |
| `.m` | matlab | `line` | parsed as text only, **never executed** |
| `.csv` | csv | `line` | text table |
| `.json` | json | `line` | structured text |
| `.txt` | simulink_export | `line` | controlled Simulink text export |

## 2. Explicitly refused

| Input | Why | What to do |
|---|---|---|
| `.slx` / `.mdl` | binary Simulink model cannot be safely interpreted | export a controlled text/CSV summary |
| `.doc` / `.xls` / `.xlsx` | legacy binary/spreadsheet formats out of P1 scope | convert to `.docx` or export CSV |
| `.exe` / `.dll` | executables are never research material | refused |
| `.zip` etc. | cannot hash/locate individual files | extract and register files individually |
| unknown suffix | no parser can be chosen | convert or declare `--kind` |

## 3. Commands and options

```powershell
# dry-run (default): shows what would be registered, writes nothing
python -m patentkit intake register .\materials --root .\workspace

# apply: manifest + materials/ copy + parsed/ cache
python -m patentkit intake register .\materials --root .\workspace --apply

# material already inside the workspace (no copy)
python -m patentkit intake register .\materials\design.md --root .\workspace --no-copy --apply

# controlled Simulink text export / larger size limit
python -m patentkit intake register .\plant_export.txt --kind simulink_export --max-bytes 10485760 --apply
```

Options: `--root/--workspace`, `--apply` (dry-run off), `--copy` (default) / `--no-copy`,
`--kind`, `--max-bytes` (default 32 MiB), `--json`.

## 4. Security boundaries (hard rules)

1. **Path confinement**: only paths inside the workspace; `..`, absolute paths and symlink escapes are rejected.
2. **Read-only**: parsers only read bytes/text; `.py`/`.m` are never imported or executed; binary models are refused.
3. **No exfiltration**: no network, no upload, no external service; `confidentiality` is always `private`.
4. **Prompt injection is data**: instruction-like text in material is stored as plain data and never changes kernel behaviour.
5. **No silent overwrite**: changed material (different hash) is a conflict requiring re-registration;
   unchanged material is skipped idempotently.

## 5. Parsed cache and locators

- Cache: `10_discovery/parsed/SRC-xxx.txt` (+ `SRC-xxx.meta.json` with locator scheme/parser version).
- `source_refs[].locator` must point into the cache: `line=42` / `lines=42-57`; `P0007` for docx
  paragraphs; `page=3` for PDF pages.
- The cache only helps locate text; **the original file is authoritative** and its manifest hash
  detects changes.

## 6. Common intake failures

| Symptom | Meaning | Fix |
|---|---|---|
| `--copy` required / source outside workspace | external material with `--no-copy` | drop `--no-copy` (copy into the private workspace) |
| `changed since registration` | material differs from the registered hash | re-register as a new source or restore the file |
| `exceeds --max-bytes` | file too large | split the material or raise the limit explicitly |
| `no extractable text pages` | scanned/image-only PDF | provide a text PDF or OCR'd text |
| `encrypted PDF` | password-protected PDF | export an unencrypted copy |
| `requires the optional dependency` | missing python-docx / pypdf | install `patentkit[docx]` / `patentkit[pdf]` |
