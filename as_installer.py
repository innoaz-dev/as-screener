# -*- coding: utf-8 -*-
"""
AS 스크리너 - 설치 관리 v0.1 (2026-11-02)

- approved/ 의 승인된 스킬을 Claude Code(기본) 또는 Codex 스킬 폴더에 설치·제거한다.
- AS 스크리너가 설치한 스킬(AS_SCREENER.json 이 있는 폴더)만 제거·덮어쓰기한다. 사용자가 만든 스킬은 건드리지 않는다.
- 변조 감지: 승인본(D:\\…\\approved)의 AS_SCREENER.json 에 기록된 파일 지문(SHA-256)이 기준이다.
  설치본 안의 기록은 믿지 않는다 (설치본 기록까지 고치면 감지를 피할 수 있으므로).
- 지문에 없는 파일이 새로 생겨도 변조로 본다 (예: 누가 스크립트를 몰래 넣은 경우).
파이썬 표준 라이브러리만 사용.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

MARKER = "AS_SCREENER.json"
EXTRA_OK = {MARKER, "LICENSE.original"}          # 지문 대상이 아닌 우리 파일
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")


class InstallError(Exception):
    """사용자에게 그대로 보여줄 한국어 오류. code 는 화면이 다음 버튼을 고를 때 쓴다."""

    def __init__(self, msg: str, code: str = "error"):
        super().__init__(msg)
        self.code = code


def home() -> Path:
    # 테스트에서는 AS_SCREENER_HOME 으로 가짜 홈 폴더를 쓴다
    return Path(os.environ.get("AS_SCREENER_HOME") or Path.home())


TARGETS = {
    "claude": ("Claude Code", lambda: home() / ".claude" / "skills"),
    "codex": ("Codex", lambda: home() / ".codex" / "skills"),
}


def target_dir(target: str) -> Path:
    if target not in TARGETS:
        raise InstallError(f"알 수 없는 설치 위치: {target}")
    return TARGETS[target][1]()


def _check_name(name: str) -> str:
    if not _NAME.match(name or ""):
        raise InstallError(f"스킬 이름이 올바르지 않습니다: {name!r}")
    return name


def _read_marker(folder: Path) -> dict | None:
    """None = 표시 파일 없음(우리가 설치한 것 아님). {} = 있지만 읽을 수 없음."""
    p = folder / MARKER
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _text_sha(p: Path) -> str | None:
    # 승인 때는 문자열(UTF-8)로 지문을 냈다. 윈도우 줄바꿈(CRLF)도 같은 글로 보도록 텍스트로 읽는다.
    try:
        return hashlib.sha256(p.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    except (OSError, UnicodeDecodeError):
        return None


def integrity(folder: Path, rec: dict | None = None) -> tuple[str, list[str]]:
    """('ok'|'modified'|'unknown', 문제 목록). rec 를 주면 그 기록(승인본)을 기준으로 비교."""
    rec = _read_marker(folder) if rec is None else rec
    files = (rec or {}).get("files")
    if not isinstance(files, dict) or not files:
        return "unknown", ["출처 기록(AS_SCREENER.json)이 없거나 읽을 수 없음"]
    problems = []
    for rel, sha in files.items():
        p = folder / rel
        if not p.is_file():
            problems.append(f"없어짐: {rel}")
        elif _text_sha(p) != sha:
            problems.append(f"바뀜: {rel}")
    for p in sorted(folder.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(folder).as_posix()
        if rel not in files and rel not in EXTRA_OK:
            problems.append(f"새로 생김: {rel}")
    return ("modified" if problems else "ok"), problems


def _approved_dir(base: Path, name: str) -> Path:
    name = _check_name(name)
    root = (base / "approved").resolve()
    src = (root / name).resolve()
    if src.parent != root or not src.is_dir():
        raise InstallError(f"승인된 스킬을 찾을 수 없습니다: {name}", "not_found")
    return src


def install_state(base: Path, name: str, target: str) -> dict:
    label = TARGETS[target][0]
    dest = target_dir(target) / name
    if not dest.exists():
        return {"label": label, "state": "none", "path": str(dest)}
    if _read_marker(dest) is None:
        return {"label": label, "state": "foreign", "path": str(dest)}
    rec = _read_marker(base / "approved" / name) or {}
    st, probs = integrity(dest, rec)
    return {"label": label, "state": "installed" if st == "ok" else "modified", "problems": probs, "path": str(dest)}


def list_skills(base: Path) -> list[dict]:
    """승인된 스킬 목록 + 설치 상태 + 변조 여부."""
    approved = base / "approved"
    out = []
    if not approved.is_dir():
        return out
    for d in sorted(p for p in approved.iterdir() if p.is_dir() and _NAME.match(p.name)):
        rec = _read_marker(d) or {}
        checks = rec.get("auto_checks") or []
        st, probs = integrity(d)
        out.append({
            "name": d.name, "source": rec.get("source", ""), "approved_at": rec.get("approved_at", ""),
            "license": rec.get("source_license", ""),
            "checks": f"{sum(c.get('status') == 'pass' for c in checks)}/{len(checks)}" if checks else "",
            "integrity": st, "problems": probs,
            "installs": {t: install_state(base, d.name, t) for t in TARGETS},
        })
    return out


def install(base: Path, name: str, target: str, overwrite: bool = False) -> Path:
    src = _approved_dir(base, name)
    rec = _read_marker(src)
    st, probs = integrity(src, rec)
    if st != "ok":
        raise InstallError("승인본이 승인 이후 바뀌었습니다. 설치하지 않습니다. 다시 검사·승인하세요: "
                           + "; ".join(probs[:5]), "tampered")
    dest_root = target_dir(target)
    dest = dest_root / src.name
    if dest.exists() or dest.is_symlink():
        if _read_marker(dest) is None:
            raise InstallError(f"같은 이름의 스킬이 이미 있습니다 (AS 스크리너가 설치한 것이 아님): {dest}\n"
                               "직접 만든 스킬은 덮어쓰지 않습니다. 다른 이름으로 다시 승인하세요.", "foreign")
        if not overwrite:
            raise InstallError("이미 설치되어 있습니다. 승인본으로 바꾸려면 '덮어쓰기'를 누르세요.", "exists")
        _remove_ours(dest)
    dest_root.mkdir(parents=True, exist_ok=True)
    tmp = dest_root / f".{src.name}.as-tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(src, tmp)
    rec = dict(rec or {})
    rec["installed"] = {"target": target, "path": str(dest), "approved_copy": str(src),
                        "installed_at": datetime.now().isoformat(timespec="seconds")}
    (tmp / MARKER).write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.rename(dest)   # 다 복사한 뒤 한 번에 이름 바꿈 → 반쯤 설치된 상태가 남지 않음
    return dest


def uninstall(name: str, target: str) -> Path:
    name = _check_name(name)
    dest = target_dir(target) / name
    if not dest.exists():
        raise InstallError("설치되어 있지 않습니다.", "not_installed")
    if _read_marker(dest) is None:
        raise InstallError("AS 스크리너가 설치한 스킬이 아니라서 지우지 않습니다.", "foreign")
    _remove_ours(dest)
    return dest


def _remove_ours(dest: Path) -> None:
    if dest.is_symlink():
        raise InstallError("바로가기(링크) 폴더는 지우지 않습니다. 직접 확인하세요.", "unsafe")
    root = dest.parent.resolve()
    real = dest.resolve()
    if real.parent != root or _read_marker(real) is None:
        raise InstallError("안전 확인 실패: 스킬 폴더 바로 아래가 아니거나 AS 스크리너 표시가 없습니다.", "unsafe")
    shutil.rmtree(real)
