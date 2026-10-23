# Patent Research Skill 2.4.0

Requires **patentkit 0.2.0, assessment protocol 1**, and Python 3.11+.

Source provenance (`evidence_level`) and judgment are now independent. Grounded AI
assessments may count toward G-S-02; G-S-03 requires explicit human confirmation of
the current candidate fingerprint. Substantive judgment or cited-passage changes
invalidate confirmation. Human decisions take priority; conflicting AI results
become proposals. History is retained, and migration never invents a reviewer.

## Download and install

Download `patent-research-skill-v2.4.0.zip`, `install-oneclick.cmd`, and the matching
`patentkit-0.2.0-py3-none-any.whl` from the [kernel release](https://github.com/cyy1018abc-kyy/patent-research-skill/releases/tag/patentkit-v0.2.0).
Keep these three files in the same directory. On Windows, double-click the CMD file;
manual PowerShell and POSIX instructions are in `INSTALL-colleagues.md`.
Use only this version pair; a source-code ZIP cannot replace the installation ZIP.
Verify the downloads against `SHA256SUMS-skill-v2.4.0.txt` and the kernel's checksum file.

The installation ZIP contains `manifest.json`, installers at its root, the
`patent-research/` payload, and an empty synthetic `samples/sample_workspace/`.
Every payload file is hashed in the manifest. Empty samples intentionally do not
pass the research acceptance gates.

## Upgrade an existing workspace

Back up the workspace first, then install the new kernel and skill. The installers
replace only the skill directory; they do not migrate research data automatically.

```bash
python -m patentkit review migrate-assessments --root /path/to/workspace
python -m patentkit review migrate-assessments --root /path/to/workspace --apply
python -m patentkit validate --root /path/to/workspace --strict
```

Migration previews changes by default. Legacy judgments become `actor: unknown`
and require evidence-backed reassessment and explicit human confirmation before
counting toward the corresponding gates. Previous gate counts may decrease.
See `patent-research/references/07-assessment-protocol.md` for the review workflow.

## Verification and limits

CI builds the actual kernel wheel and installation ZIP, verifies checksums and
repeatable ZIP output, and checks protocol behavior, sample execution, installation,
upgrade, uninstall and legacy migration on Windows/Linux with Python 3.11/3.12.
PowerShell and POSIX installer tests run on their respective supported runners.
The new kernel regression suite contains 31 cases. The upstream source archive
omits fixtures required by parts of its older suite; this release does not claim
that the entire upstream suite was executed. Client UI discovery is not automated.

No real patent data is included. Recorded reviewer names are audit metadata, not
identity authentication; quote matching does not establish semantic correctness.
