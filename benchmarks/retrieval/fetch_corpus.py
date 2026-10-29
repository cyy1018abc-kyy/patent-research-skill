#!/usr/bin/env python3
"""冻结 DAPFAM 公开评测语料（Phase V / V1-2）——下载、校验、SHA-256 清单。

许可边界（docs/retrieval-evaluation.md 附录 A）：CC-BY-NC-SA-4.0，语料本体
**只存本地**（`benchmarks/retrieval/corpus/` 已 gitignore），绝不进入任何发行
资产；报告只引用聚合数字并携带署名。

用法：
    python benchmarks/retrieval/fetch_corpus.py                # 下载 + 校验 + 清单
    python benchmarks/retrieval/fetch_corpus.py --endpoint https://hf-mirror.com
    python benchmarks/retrieval/fetch_corpus.py --manifest-only  # 只重算清单

下载通道探测结论（2026-10-29，附录 A.3）：huggingface.co 直连不可达，
`https://hf-mirror.com` 可达——--endpoint 默认值即它。
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = Path(__file__).resolve().parent / "corpus" / "dapfam"
DATASET = "datalyes/DAPFAM_patent"
DEFAULT_ENDPOINT = "https://hf-mirror.com"
FILES = ("qrels_all.parquet", "queries.parquet", "corpus.parquet")

EXPECTED_BYTES = {  # HF 主树 2026-10-29 快照；不符即拒绝（防截断/换源静默漂移）
    "corpus.parquet": 1_096_700_000,
    "queries.parquet": 59_800_000,
    "qrels_all.parquet": 800_000,
}


def _sha256(path: Path, *, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def probe(endpoint: str) -> bool:
    url = f"{endpoint}/api/datasets/{DATASET}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            ok = resp.status == 200
    except OSError:
        ok = False
    print(f"[probe] {endpoint} -> {'OK' if ok else 'UNREACHABLE'}")
    return ok


def fetch(endpoint: str) -> int:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    failures = []
    for name in FILES:
        dest = CORPUS_DIR / name
        url = f"{endpoint}/datasets/{DATASET}/resolve/main/{name}"
        for attempt in range(3):
            proc = subprocess.run(
                ["curl", "-sL", "--connect-timeout", "15", "--retry", "2", "-C", "-", "-o", str(dest), url],
                check=False)
            if proc.returncode == 0:
                break
            time.sleep(5 * (attempt + 1))
        else:
            failures.append(name)
            continue
        size = dest.stat().st_size
        note = "ok" if size >= EXPECTED_BYTES[name] else "TRUNCATED?"
        print(f"[fetch] {name}: {size} bytes ({note})")
        if note != "ok":
            failures.append(name)
    return len(failures)


def write_manifest() -> int:
    lines = []
    for name in sorted(p.name for p in CORPUS_DIR.glob("*.parquet")):
        lines.append(f"{_sha256(CORPUS_DIR / name)}  {name}")
        print(f"[sha256] {name} {_sha256(CORPUS_DIR / name)[:16]}…")
    manifest = CORPUS_DIR / "MANIFEST.sha256"
    with open(manifest, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"[manifest] {manifest}")
    return 0


def _pin_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main() -> int:
    _pin_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="HF API endpoint（默认镜像）")
    parser.add_argument("--manifest-only", action="store_true", help="跳过下载，只重算 SHA-256 清单")
    args = parser.parse_args()
    if args.manifest_only:
        return write_manifest()
    if not probe(args.endpoint):
        print("[FATAL] endpoint 不可达；用 --endpoint 指定可用镜像或人工放置文件后 --manifest-only", file=sys.stderr)
        return 2
    return 1 if fetch(args.endpoint) else write_manifest()


if __name__ == "__main__":
    sys.exit(main())
