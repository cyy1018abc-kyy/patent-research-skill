"""从技能源码和已安装内核生成可重复、可校验的正式安装包（多技能，schema 2）。

v3.0.0 起一个发布动作产出两个包：
- patent-research-skill-v<版本>.zip   全量包（patent-research + patent-drafting + 样例）
- patent-drafting-skill-v<版本>.zip   单技能包（仅 patent-drafting，无样例）

两个包共用同一套安装器：安装器按 manifest.skills 枚举载荷目录，装几个算几个。
"""

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
#: 源码目录 → 载荷目录名（= SKILL.md 的 name；目录名必须与之对应）
SKILL_DIRS = ("research", "drafting")
KERNEL_VERSION = "0.5.0"
#: 单技能包只发 drafting（research 单装没有意义：drafting 依赖它，全量包已含）
SINGLE_SKILLS = ("drafting",)


def _collect_payload(source_dir: Path, install_name: str) -> dict[str, bytes]:
    files = {}
    for path in sorted(source_dir.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Symlinks cannot enter a release: {path}")
        if path.is_file() and not any(p.startswith(".") or p == "__pycache__" for p in path.relative_to(source_dir).parts) and path.suffix not in {".pyc", ".pyo"}:
            files[f"{install_name}/{path.relative_to(source_dir).as_posix()}"] = path.read_bytes()
    return files


def _skill_meta(source_dir: Path) -> dict:
    frontmatter = yaml.safe_load((source_dir / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1])
    name, version = frontmatter["name"], str(frontmatter["metadata"]["version"])
    if name != f"patent-{source_dir.name}" or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError(f"Invalid skill name/version in {source_dir.name}: {name} {version}")
    return {"name": name, "version": version, "install_dir": name, "source_dir": source_dir.name}


def _write_zip(path: Path, files: dict[str, bytes], stamp: datetime) -> None:
    from patentkit.init import DIRS

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if "samples/sample_workspace/README.md" in files:
            for directory in DIRS:
                info = zipfile.ZipInfo(f"samples/sample_workspace/{directory}/", stamp.astimezone(timezone.utc).timetuple()[:6])
                info.create_system = 3
                info.external_attr = (0o40755 << 16) | 0x10
                archive.writestr(info, b"")
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, stamp.astimezone(timezone.utc).timetuple()[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith(".sh") else 0o100644) << 16
            archive.writestr(info, data)


def build(out: Path, built_at: str) -> dict:
    import patentkit
    from patentkit import api
    from patentkit.assessment import PROTOCOL_VERSION
    from patentkit.init import init_workspace

    if patentkit.__version__ != KERNEL_VERSION or PROTOCOL_VERSION != 1:
        raise ValueError(f"Build requires patentkit {KERNEL_VERSION} with assessment protocol 1")
    stamp = datetime.fromisoformat(built_at)
    if stamp.tzinfo is None:
        raise ValueError("--built-at must include a timezone")

    metas = [_skill_meta(ROOT / d) for d in SKILL_DIRS]
    versions = {m["version"] for m in metas}
    if len(versions) != 1:
        raise ValueError(f"Skill versions must be paired, got {sorted(versions)}")
    version = versions.pop()

    payloads = {m["source_dir"]: _collect_payload(ROOT / m["source_dir"], m["install_dir"]) for m in metas}

    samples: dict[str, bytes] = {}
    with tempfile.TemporaryDirectory(prefix="patent-release-") as temp:
        sample = Path(temp) / "sample_workspace"
        init_workspace(sample, "TGT-0002", "Synthetic release sample")
        for path in sample.rglob("*"):
            if path.is_file():
                content = path.read_text(encoding="utf-8").replace(datetime.now().date().isoformat(), stamp.date().isoformat())
                samples[f"samples/sample_workspace/{path.relative_to(sample).as_posix()}"] = content.replace("\r\n", "\n").encode("utf-8")
        if not api.validate(sample, strict=True)["ok"]:
            raise ValueError("Invalid sample workspace")
    samples["samples/sample_workspace/README.md"] = b"# Synthetic workspace\n\nEmpty synthetic data for installation checks; no gates are expected to pass.\n"

    def assemble(skill_keys: tuple[str, ...], with_samples: bool) -> dict[str, bytes]:
        files: dict[str, bytes] = {}
        for key in skill_keys:
            files.update(payloads[key])
        for filename in INSTALL_FILES:
            files[filename] = (ROOT / "release" / filename).read_bytes()
        files["LICENSE"] = (ROOT / "LICENSE").read_bytes()
        if with_samples:
            files.update(samples)
        return files

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()

    # 已有公开示例只使用占位编号；真实目标和公开号不能进入安装包。
    def leak_guard(files: dict[str, bytes]) -> None:
        for path, content in files.items():
            if re.search(r"\bTGT-000[01]\b|\bCN\d{6,}[A-Z]?\b", content.decode("utf-8")):
                raise ValueError(f"Possible real target ID or publication number in {path}")

    def manifest_for(skill_keys: tuple[str, ...], files: dict[str, bytes]) -> bytes:
        selected = [m for m in metas if m["source_dir"] in skill_keys]
        manifest = {
            "schema_version": 2, "package": "patent-research-skill", "built_at": built_at,
            "skills": [{k: v for k, v in m.items() if k != "source_dir"} for m in selected],
            "compat": {"python": ">=3.11", "patentkit": f">={KERNEL_VERSION}", "assessment_protocol": 1},
            "source": {"commit": commit},
            "contents": {
                "references": {m["install_dir"]: len(list((ROOT / m["source_dir"] / "references").glob("*.md"))) for m in selected},
                "samples_included": "samples/sample_workspace/README.md" in files,
            },
            "files": [{"path": p, "size": len(d), "sha256": hashlib.sha256(d).hexdigest()} for p, d in sorted(files.items())],
        }
        return (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    out.mkdir(parents=True, exist_ok=True)
    products = {}

    # 全量包：两个技能 + 样例
    full_files = assemble(SKILL_DIRS, with_samples=True)
    leak_guard(full_files)
    full_files["manifest.json"] = manifest_for(SKILL_DIRS, full_files)
    full_zip = out / f"patent-research-skill-v{version}.zip"
    _write_zip(full_zip, full_files, stamp)
    products["full"] = {"zip": str(full_zip.resolve()), "sha256": hashlib.sha256(full_zip.read_bytes()).hexdigest()}

    # 单技能包：drafting（无样例；安装器自检自动降级为 SKILL.md 存在性检查）
    single_files = assemble(SINGLE_SKILLS, with_samples=False)
    leak_guard(single_files)
    single_files["manifest.json"] = manifest_for(SINGLE_SKILLS, single_files)
    single_zip = out / f"patent-drafting-skill-v{version}.zip"
    _write_zip(single_zip, single_files, stamp)
    products["drafting"] = {"zip": str(single_zip.resolve()), "sha256": hashlib.sha256(single_zip.read_bytes()).hexdigest()}

    guide = out / "INSTALL-colleagues.md"
    guide.write_bytes(full_files["install-guide-for-colleagues.md"])
    installer = out / "install-oneclick.cmd"
    installer.write_bytes(full_files[installer.name])
    (out / f"SHA256SUMS-skill-v{version}.txt").write_text(
        "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n"
                for p in (full_zip, single_zip, guide, installer)),
        encoding="utf-8")
    return {
        "zips": products,
        "version": version,
        "skills": [m["name"] for m in metas],
        "checksums": str((out / f"SHA256SUMS-skill-v{version}.txt").resolve()),
        "manifest": json.loads(manifest_for(SKILL_DIRS, full_files)),
    }


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
    print(json.dumps(result, ensure_ascii=True) if args.json else "\n".join(
        f"{key}: {value['zip']} ({value['sha256'][:12]}…)" for key, value in result["zips"].items()))
    return 0


if __name__ == "__main__":
    main()
