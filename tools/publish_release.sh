#!/usr/bin/env bash
# 只上传本次工作流已验收的产物；两份草稿都就绪后才公开。
set -euo pipefail

kernel=patentkit-v0.6.0
skill=skill-v3.4.0
published=0
for tag in "$kernel" "$skill"; do
    if draft=$(gh release view "$tag" --json isDraft --jq '.isDraft'); then
        if [ "$draft" = false ]; then
            published=$((published + 1))
            continue
        fi
        target=$(gh release view "$tag" --json targetCommitish --jq '.targetCommitish')
        [ "$target" = "$GITHUB_SHA" ] || { echo "Draft $tag targets another commit" >&2; exit 1; }
    else
        gh release create "$tag" --target "$GITHUB_SHA" --draft --title "$tag" --notes-file "release/notes/$tag.md"
    fi
done
[ "$published" -eq 2 ] && exit 0

if [ "$(gh release view "$kernel" --json isDraft --jq '.isDraft')" = true ]; then
    gh release upload "$kernel" dist/patentkit-0.6.0-py3-none-any.whl dist/patentkit-0.6.0.tar.gz dist/SHA256SUMS-patentkit-v0.6.0.txt --clobber
fi
if [ "$(gh release view "$skill" --json isDraft --jq '.isDraft')" = true ]; then
    gh release upload "$skill" dist/patent-research-skill-v3.4.0.zip dist/patent-drafting-skill-v3.4.0.zip dist/INSTALL-colleagues.md dist/install-oneclick.cmd dist/SHA256SUMS-skill-v3.4.0.txt --clobber
fi
gh release edit "$kernel" --draft=false --latest=false
gh release edit "$skill" --draft=false --latest=true
