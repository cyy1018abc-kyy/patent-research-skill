"""O-01/O-03/O-04: extension wheel build, fresh-venv install acceptance, doctor checks.

F-02 acceptance realized end-to-end: the wheel installs into a clean venv with zero
third-party deps, `python -m patent_intel --help` works offline, and the wheel is
uninstallable. The doctor's extension check audits SUMS + METADATA.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_skill_release", REPO_ROOT / "tools" / "build_skill_release.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_doctor():
    spec = importlib.util.spec_from_file_location("release_doctor", REPO_ROOT / "tools" / "release_doctor.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def built_extension(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("extension-build")
    builder = _load_builder()
    builder.build_extension_wheel(out)
    return out / "extension"


@pytest.fixture(scope="session")
def wheel_path(built_extension: Path) -> Path:
    wheels = list(built_extension.glob("patent_intel-*.whl"))
    assert len(wheels) == 1
    return wheels[0]


# ── wheel build + SUMS (O-03) ────────────────────────────────────────


def test_extension_wheel_and_sums(built_extension: Path, wheel_path: Path) -> None:
    sums = built_extension / f"SHA256SUMS-patent-intel-v0.1.0.txt"
    assert sums.is_file()
    import hashlib

    digest = hashlib.sha256(wheel_path.read_bytes()).hexdigest()
    assert sums.read_text(encoding="utf-8") == f"{digest}  {wheel_path.name}\n"
    assert wheel_path.name == "patent_intel-0.1.0-py3-none-any.whl"


def test_extension_wheel_metadata_minimal_install(wheel_path: Path) -> None:
    """O-01: 最小安装不拉取模型/数据库/GPU 运行时 — base deps 空、extras 齐全。"""
    with zipfile.ZipFile(wheel_path) as archive:
        metadata_name = next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
        metadata = archive.read(metadata_name).decode("utf-8")
    base_requires = [
        line.split(":", 1)[1].strip()
        for line in metadata.splitlines()
        if line.startswith("Requires-Dist:")
        and "extra ==" not in line
    ]
    assert base_requires == []
    for extra in ("kernel", "pdf", "dense", "ops"):
        assert f"extra =='{extra}'" in metadata or f'extra == "{extra}"' in metadata or f"extra =='{extra}'" in metadata
    assert "Requires-Python: >=3.11" in metadata


def test_extension_wheel_pure_python_content(wheel_path: Path) -> None:
    with zipfile.ZipFile(wheel_path) as archive:
        names = archive.namelist()
    assert all(n.startswith(("patent_intel/", "patent_intel-0.1.0.dist-info/")) for n in names)
    # no binaries, no bundled models
    assert not any(n.endswith((".so", ".pyd", ".dll", ".bin", ".onnx", ".safetensors")) for n in names)


# ── fresh venv install acceptance (F-02/O-01) ────────────────────────


@pytest.mark.slow
def test_fresh_venv_install_help_doctor_uninstall(wheel_path: Path, tmp_path: Path) -> None:
    venv = tmp_path / "venv"
    create = subprocess.run(
        [sys.executable, "-m", "venv", str(venv)],
        capture_output=True, text=True, timeout=300, check=False,
    )
    assert create.returncode == 0, create.stderr
    python = venv / "Scripts" / "python.exe" if sys.platform == "win32" else venv / "bin" / "python"

    def run(*args: str, timeout: int = 300) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(python), *args], capture_output=True, text=True, encoding="utf-8", timeout=timeout, check=False,
        )

    # --help works in the empty venv BEFORE install (stdlib-only module via wheel? no—) 
    # ...before install the module doesn't exist yet; install first (no deps pulled):
    install = run("-m", "pip", "install", str(wheel_path), "--no-deps", "--quiet")
    assert install.returncode == 0, install.stderr

    help_run = run("-m", "patent_intel", "--help")
    assert help_run.returncode == 0
    assert "doctor" in help_run.stdout

    doctor = run("-m", "patent_intel", "doctor")
    assert doctor.returncode == 0
    assert "offline" in doctor.stdout

    version = run("-c", "import patent_intel; print(patent_intel.__version__)")
    assert version.stdout.strip() == "0.1.0"

    # uninstallable
    uninstall = run("-m", "pip", "uninstall", "-y", "patent-intel", "--quiet")
    assert uninstall.returncode == 0
    gone = run("-m", "patent_intel", "--version")
    assert gone.returncode != 0


# ── doctor extension check (O-04) ────────────────────────────────────


def test_doctor_extension_check_pass_and_skip(built_extension: Path, tmp_path: Path) -> None:
    doctor = _load_doctor()
    # present + consistent → PASS
    status, detail = doctor.check_extension_wheel_files(built_extension.parent)
    assert status == doctor.PASS, detail
    # absent → SKIP (optional component, never blocks a skill release)
    status, detail = doctor.check_extension_wheel_files(tmp_path)
    assert status == doctor.SKIP


def test_doctor_extension_check_detects_tampering(built_extension: Path) -> None:
    doctor = _load_doctor()
    tampered = built_extension.parent.parent / "tampered-dist"
    import shutil

    target = tampered / "extension"
    shutil.copytree(built_extension, target)
    wheel = next(target.glob("patent_intel-*.whl"))
    # rewrite one file inside the wheel (zip append with same name creates a second entry)
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr("patent_intel/__init__.py", "# tampered\n")
    status, detail = doctor.check_extension_wheel_files(tampered)
    assert status == doctor.FAIL
    assert "sha256" in detail


def test_doctor_extension_check_detects_bad_metadata(tmp_path: Path) -> None:
    import hashlib

    doctor = _load_doctor()
    ext = tmp_path / "extension"
    ext.mkdir()
    bad = ext / "patent_intel-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(bad, "w") as archive:
        archive.writestr(
            "patent_intel-0.1.0.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: patent-intel\nVersion: 0.1.0\n"
            "Requires-Python: >=3.11\nRequires-Dist: torch\n",
        )
        archive.writestr(
            "patent_intel-0.1.0.dist-info/entry_points.txt",
            "[console_scripts]\n",
        )
        archive.writestr("patent_intel/__init__.py", "")
    digest = hashlib.sha256(bad.read_bytes()).hexdigest()
    (ext / "SHA256SUMS-patent-intel-v0.1.0.txt").write_text(f"{digest}  {bad.name}\n", encoding="utf-8")
    status, detail = doctor.check_extension_wheel_files(tmp_path)
    assert status == doctor.FAIL
    assert "torch" in detail or "extras" in detail


# ── builder result wiring (O-03) ─────────────────────────────────────


def test_build_result_reports_extension(tmp_path: Path) -> None:
    builder = _load_builder()
    result = builder.build_extension_wheel(tmp_path)
    assert result["version"] == "0.1.0"
    assert Path(result["wheel"]).is_file()
    assert Path(result["checksums"]).is_file()
    assert len(result["sha256"]) == 64


_ = json  # import guard
