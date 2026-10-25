"""从技能源码和已安装内核生成可重复、可校验的正式安装包。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INSTALL_FILES = ("install.ps1", "install.sh", "install-oneclick.cmd", "INSTALL.md", "install-guide-for-colleagues.md")


def build(out: Path, built_at: str) -> dict:
    import patentkit
    from patentkit import api
    from patentkit.assessment import PROTOCOL_VERSION
    from patentkit.init import DIRS, init_workspace

    if patentkit.__version__ != "0.3.0" or PROTOCOL_VERSION != 1:
        raise ValueError("Build requires patentkit 0.3.0 with assessment protocol 1")
    stamp = datetime.fromisoformat(built_at)
    if stamp.tzinfo is None:
        raise ValueError("--built-at must include a timezone")
    source = ROOT / "patent-research-skill"
    frontmatter = yaml.safe_load((source / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1])
    name, version = frontmatter["name"], str(frontmatter["metadata"]["version"])
    if name != "patent-research" or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Invalid skill name/version")
    files = {}
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Symlinks cannot enter a release: {path}")
        if path.is_file() and not any(p.startswith(".") or p == "__pycache__" for p in path.relative_to(source).parts) and path.suffix not in {".pyc", ".pyo"}:
            files[f"{name}/{path.relative_to(source).as_posix()}"] = path.read_bytes()
    for filename in INSTALL_FILES:
        files[filename] = (ROOT / "release" / filename).read_bytes()
    files["LICENSE"] = (ROOT / "LICENSE").read_bytes()
    with tempfile.TemporaryDirectory(prefix="patent-release-") as temp:
        sample = Path(temp) / "sample_workspace"
        init_workspace(sample, "TGT-0002", "Synthetic release sample")
        for path in sample.rglob("*"):
            if path.is_file():
                content = path.read_text(encoding="utf-8").replace(datetime.now().date().isoformat(), stamp.date().isoformat())
                files[f"samples/sample_workspace/{path.relative_to(sample).as_posix()}"] = content.replace("\r\n", "\n").encode("utf-8")
        result = api.validate(sample, strict=True)
        if not result["ok"]:
            raise ValueError(f"Invalid sample workspace: {result['findings']}")
    files["samples/sample_workspace/README.md"] = b"# Synthetic workspace\n\nEmpty synthetic data for installation checks; no gates are expected to pass.\n"
    # 已有公开示例只使用占位编号；真实目标和公开号不能进入安装包。
    for path, content in files.items():
        if re.search(r"\bTGT-000[01]\b|\bCN\d{6,}[A-Z]?\b", content.decode("utf-8")):
            raise ValueError(f"Possible real target ID or publication number in {path}")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    manifest = {
        "schema_version": 1, "package": "patent-research-skill", "built_at": built_at,
        "skill": {"name": name, "version": version, "install_dir": name},
        "compat": {"python": ">=3.11", "patentkit": ">=0.3.0", "assessment_protocol": 1},
        "source": {"commit": commit},
        "contents": {"references": len(list((source / "references").glob("*.md"))), "samples_included": True},
        "files": [{"path": p, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()} for p, data in sorted(files.items())],
    }
    files["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    out.mkdir(parents=True, exist_ok=True)
    package = out / f"patent-research-skill-v{version}.zip"
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for directory in DIRS:
            info = zipfile.ZipInfo(f"samples/sample_workspace/{directory}/", stamp.astimezone(timezone.utc).timetuple()[:6])
            info.create_system = 3
            info.external_attr = (0o40755 << 16) | 0x10
            archive.writestr(info, b"")
        for path, data in sorted(files.items()):
            info = zipfile.ZipInfo(path, stamp.astimezone(timezone.utc).timetuple()[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100755 if path.endswith(".sh") else 0o100644) << 16
            archive.writestr(info, data)
    checksum = hashlib.sha256(package.read_bytes()).hexdigest()
    sums = out / f"SHA256SUMS-skill-v{version}.txt"
    guide = out / "INSTALL-colleagues.md"
    guide.write_bytes(files["install-guide-for-colleagues.md"])
    installer = out / "install-oneclick.cmd"
    installer.write_bytes(files[installer.name])
    sums.write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in (package, guide, installer)), encoding="utf-8")
    return {"zip": str(package.resolve()), "sha256": checksum, "manifest": manifest, "checksums": str(sums.resolve())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    parser.add_argument("--built-at", default=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = build(args.out, args.built_at)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Build failed: {exc}\n")
    print(json.dumps(result, ensure_ascii=True) if args.json else result["zip"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
