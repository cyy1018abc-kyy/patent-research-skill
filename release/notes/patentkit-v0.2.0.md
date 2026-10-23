# patentkit 0.2.0

Companion kernel for Patent Research Skill 2.4.0; Python 3.11+.

- Separate source provenance from assessment actor, original-text support and
  fingerprint-bound human confirmation (assessment protocol 1).
- Count grounded AI assessments for G-S-02 and require current human confirmation
  for G-S-03. Preserve human decisions and judgment history.
- Add JSON assessment export/import, explicit batch confirmation and conservative
  schema migration. Legacy CSV edits cannot fabricate confirmation.
- Apply the same rules to gates, validation, status, reports and API callers.

Assets: `patentkit-0.2.0-py3-none-any.whl`, `patentkit-0.2.0.tar.gz`, and
`SHA256SUMS-patentkit-v0.2.0.txt`. The kernel is reconstructed in CI from the
checksum-verified public 0.1.2 source and the repository's complete source patch.

```bash
python -m pip install ./patentkit-0.2.0-py3-none-any.whl
python -m patentkit review migrate-assessments --root /path/to/workspace
# After checking the preview and backing up the workspace:
python -m patentkit review migrate-assessments --root /path/to/workspace --apply
```

Existing source grades are preserved. Legacy judgments without provenance stay
unknown; old scores and role labels do not imply human approval. Gate counts may
decrease until supported assessments and explicit confirmations are supplied.

The actual built wheel is installed before release acceptance. All 31 new behavior
regressions run in CI. Some older upstream tests require fixtures omitted from the
public source archive, so full upstream-suite coverage is not claimed.
See the [skill release](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/skill-v2.4.0)
for the paired installer, migration instructions and limits.
