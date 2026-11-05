# -*- coding: utf-8 -*-
"""
AS 스크리너 - 붙여넣기 폼 시제품 v0.10.2 (2026-11-04)

사용법: AS스크리너.bat 더블클릭 (또는 `uv run --python 3.12 as_screener.py`)
- 내 PC 안(127.0.0.1)에서만 열리는 검사 화면을 브라우저로 띄운다.
- 깃허브 주소 / 폴더 경로 / SKILL.md 본문 중 아무거나 붙여넣고 [검사하기].
- 1차: SkillSpector 정적 검사 + 우리 규칙(rules/ko 한국어, rules/zh 중국어, rules/ja 일본어). 무료, 수 초.
- 2차(선택): LLM 정밀검사(claude_cli). Claude 사용량 소모, 30~60초.
- 검사 대상 스킬의 코드는 절대 실행하지 않는다 (SkillSpector는 읽기만 함).
- 승인된 스킬은 '내 스킬'에서 Claude Code·Codex 스킬 폴더로 설치·제거 (v0.8).

파이썬 표준 라이브러리만 사용.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import as_rewriter as rw  # noqa: E402  같은 폴더의 재작성 엔진
import as_installer as ins  # noqa: E402  설치 관리

SESSIONS: dict = {}   # 검사 결과 → 재작성 단계로 넘길 정보
REWRITES: dict = {}   # 재작성 결과 → 승인 단계로 넘길 정보
_STORE_LOCK = threading.Lock()

VERSION = "0.10.2"
HOST = "127.0.0.1"
PORT = int(os.environ.get("AS_SCREENER_PORT", "8765"))
BASE_DIR = Path(__file__).resolve().parent
RULES_DIR = BASE_DIR / "rules"   # 하위 폴더(ko, zh, ja)까지 SkillSpector가 모두 읽음
TOKEN = secrets.token_urlsafe(24)  # 다른 웹사이트가 이 서버로 요청을 못 보내게 막는 1회용 열쇠
SCAN_TIMEOUT = 1200
MAX_PASTE_BYTES = 512 * 1024

# ── 우리 규칙 설명 (SkillSpector가 붙이는 영어 권고문 대신 표시) ─────────────────
KO_RULES = {
    "ko_credential_exfiltration": ("비밀 정보 외부 유출", "SSH 키·비밀번호·토큰 등을 외부로 보내라는 지시가 있습니다. 설치하지 마세요."),
    "ko_instruction_override": ("이전 지시 무시", "에이전트의 기존 지시·안전 지침을 무시하게 만드는 문장입니다."),
    "ko_concealment_from_user": ("사용자에게 숨기기", "사용자에게 알리지 말라는 은폐 지시입니다. 정상 스킬은 사용자에게 숨길 이유가 없습니다."),
    "ko_anti_refusal": ("탈옥 문구", "'제한이 없다', '거절하지 마라' 같은 안전장치 해제 문구입니다."),
    "ko_credential_access": ("비밀 정보 읽기", "SSH 키·환경변수 파일·지갑 등 민감한 파일을 읽으라는 지시입니다."),
    "ko_stealth_wording": ("은밀 실행", "'몰래 전송' 같이 들키지 않게 실행하라는 표현입니다."),
    "zh_credential_exfiltration": ("비밀 정보 외부 유출 (중국어)", "SSH 키·비밀번호·토큰 등을 외부로 보내라는 중국어 지시가 있습니다. 설치하지 마세요."),
    "zh_instruction_override": ("이전 지시 무시 (중국어)", "에이전트의 기존 지시·안전 지침을 무시하게 만드는 중국어 문장입니다."),
    "zh_concealment_from_user": ("사용자에게 숨기기 (중국어)", "사용자에게 알리지 말라는 중국어 은폐 지시입니다."),
    "zh_anti_refusal": ("탈옥 문구 (중국어)", "'제한이 없다', '거절하지 마라' 같은 중국어 안전장치 해제 문구입니다."),
    "zh_credential_access": ("비밀 정보 읽기 (중국어)", "SSH 키·지갑·브라우저 비밀번호 등 민감한 파일을 읽으라는 중국어 지시입니다."),
    "zh_stealth_wording": ("은밀 실행 (중국어)", "'偷偷发送(몰래 전송)' 같이 들키지 않게 실행하라는 중국어 표현입니다."),
    "ja_credential_exfiltration": ("비밀 정보 외부 유출 (일본어)", "SSH 키·비밀번호·토큰 등을 외부로 보내라는 일본어 지시가 있습니다. 설치하지 마세요."),
    "ja_instruction_override": ("이전 지시 무시 (일본어)", "에이전트의 기존 지시·안전 지침을 무시하게 만드는 일본어 문장입니다."),
    "ja_concealment_from_user": ("사용자에게 숨기기 (일본어)", "사용자에게 알리지 말라는 일본어 은폐 지시입니다."),
    "ja_anti_refusal": ("탈옥 문구 (일본어)", "'제한이 없다', '거절하지 마라' 같은 일본어 안전장치 해제 문구입니다."),
    "ja_credential_access": ("비밀 정보 읽기 (일본어)", "SSH 키·지갑·브라우저 비밀번호 등 민감한 파일을 읽으라는 일본어 지시입니다."),
    "ja_stealth_wording": ("은밀 실행 (일본어)", "'こっそり送信(몰래 전송)' 같이 들키지 않게 실행하라는 일본어 표현입니다."),
    "ko_instruction_override_weak": ("기존 지시 밀어내기 의심", "'이 문서만 따르라' 같이 기존 지시를 밀어내는 표현입니다. 내용을 확인하세요."),
    "ko_conceal_weak": ("사용자에게 알리지 말라는 의심 표현", "사용자에게 말하지 말라는 표현입니다. 정상적인 화면 안내일 수도 있으니 내용을 확인하세요."),
    "ko_secret_collection": ("비밀 정보 수집 의심", ".env·환경변수·토큰을 모으라는 표현입니다. 내용을 확인하세요."),
    "zh_instruction_override_weak": ("기존 지시 밀어내기 의심 (중국어)", "'이 문서만 따르라' 같이 기존 지시를 밀어내는 중국어 표현입니다. 내용을 확인하세요."),
    "zh_secret_collection": ("비밀 정보 수집 의심 (중국어)", ".env·환경변수·토큰을 모으라는 중국어 표현입니다. 내용을 확인하세요."),
    "ja_instruction_override_weak": ("기존 지시 밀어내기 의심 (일본어)", "'이 문서만 따르라' 같이 기존 지시를 밀어내는 일본어 표현입니다. 내용을 확인하세요."),
    "ja_conceal_weak": ("사용자에게 알리지 말라는 의심 표현 (일본어)", "사용자에게 말하지 말라는 일본어 표현입니다. 정상적인 화면 안내일 수도 있으니 내용을 확인하세요."),
    "ja_secret_collection": ("비밀 정보 수집 의심 (일본어)", ".env·환경변수·토큰을 모으라는 일본어 표현입니다. 내용을 확인하세요."),
}
OUR_PREFIX = {"ko_": "한국어 규칙", "zh_": "중국어 규칙", "ja_": "일본어 규칙"}

# SkillSpector 기본 규칙 ID 접두어 → 한국어 분류
ID_PREFIX_KO = [
    ("SDI", "LLM: 설명과 실제 동작 불일치"), ("SQP", "LLM: 품질·정책 위반"), ("SSD", "LLM: 보안 위험 발견"),
    ("AR", "탈옥·거절 무력화"), ("PE", "권한 상승·비밀 정보 접근"), ("DE", "데이터 유출"),
    ("SC", "공급망 위험"), ("EA", "과도한 권한"), ("TM", "도구 오용"), ("MP", "메모리 오염"),
    ("SP", "시스템 프롬프트 유출"), ("RA", "폭주 에이전트"), ("TT", "위험한 데이터 흐름"),
    ("TP", "도구 설명 오염(MCP)"), ("MCP", "MCP 권한"), ("YR", "악성 패턴(YARA)"),
    ("OH", "출력 처리"), ("AS", "스킬 간 접근"), ("P", "프롬프트 인젝션"),
]
SEV_KO = {"CRITICAL": "치명", "HIGH": "높음", "MEDIUM": "중간", "LOW": "낮음", "INFO": "참고"}

# SkillSpector 규칙 ID별 한국어 이름 (README 규칙표 기준)
ID_KO = {
    "P1": "지시 덮어쓰기", "P2": "숨은 지시문", "P3": "유출 명령", "P4": "행동 조작", "P5": "유해 콘텐츠",
    "P6": "직접 정보 누출", "P7": "간접 정보 추출", "P8": "도구를 통한 유출", "P9": "공백 숨김",
    "AR1": "거절 억제", "AR2": "경고문 억제", "AR3": "안전 정책 무력화",
    "E1": "외부 전송", "E2": "환경변수 수집", "E3": "파일 시스템 탐색", "E4": "맥락 누출",
    "PE1": "과도한 권한", "PE2": "관리자(sudo) 실행", "PE3": "비밀 정보 접근",
    "SC1": "버전 미고정 의존성", "SC2": "외부 스크립트 다운로드", "SC3": "난독화 코드", "SC4": "취약 의존성",
    "SC5": "방치된 의존성", "SC6": "유사 이름 패키지", "SC8": "컴파일된 파이썬 파일 포함", "SC9": "숨겨진 실행 파일",
    "SC10": "의존성 출처 변경",
    "EA1": "도구 무제한 사용", "EA2": "자율 판단", "EA3": "범위 확장", "EA4": "자원 무제한 접근", "EA5": "외부 모델 선택",
    "OH1": "검증 없는 출력 주입", "OH2": "맥락 간 출력", "OH3": "무제한 출력",
    "MP1": "지속 맥락 주입", "MP2": "맥락 채우기", "MP3": "메모리 조작", "TM1": "도구 인자 악용", "TM2": "도구 연쇄 악용",
    "TM3": "위험한 기본값", "RA1": "자기 수정", "RA2": "세션 지속", "TR1": "너무 넓은 실행 조건",
    "TR2": "숨은 명령 실행 조건", "TR3": "키워드 미끼",
    "AST1": "exec() 호출", "AST2": "eval() 호출", "AST3": "동적 import", "AST4": "외부 명령 실행(subprocess)",
    "AST5": "os.system 실행", "AST6": "compile() 호출", "AST7": "동적 getattr", "AST8": "위험한 실행 연쇄",
    "AST9": "반사적 getattr",
    "TT1": "위험한 데이터 흐름", "TT2": "변수 경유 위험 흐름", "TT3": "비밀 정보 유출 연쇄", "TT4": "파일 읽기 → 외부 전송",
    "TT5": "외부 입력 → 코드 실행",
    "YR1": "악성코드 패턴", "YR2": "웹셸 패턴", "YR3": "채굴기 패턴", "YR4": "해킹 도구 패턴",
    "LP1": "권한 과소 신고", "LP2": "와일드카드 권한", "LP3": "권한 미신고", "LP4": "권한 과다 신고",
    "AS3": "다른 스킬 파일 열람",
    "TP1": "도구 설명 속 숨은 지시", "TP2": "유니코드 위장", "TP3": "인자 설명 주입", "TP4": "설명과 동작 불일치",
}


def clean_snippet(text: str) -> str:
    """잘린 한글 조각(�) 제거, 마지막 3줄(걸린 문장이 보통 끝에 옴)·240자로 줄임."""
    text = text.replace("�", "").strip("\n")
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()][-3:]
    out = "\n".join(lines)
    return out[:240] + ("…" if len(out) > 240 else "")


def ko_category(rule_id: str) -> str:
    if rule_id.upper() in ID_KO:
        return ID_KO[rule_id.upper()]
    for prefix, label in ID_PREFIX_KO:
        if rule_id.upper().startswith(prefix):
            return label
    return "기타"


# ── 사전 점검 ────────────────────────────────────────────────────────────────
def _run_quick(argv: list[str], timeout: int = 20) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(argv, capture_output=True, timeout=timeout, env=_child_env(False))
    except (OSError, subprocess.TimeoutExpired):
        return None


_PRECHECK_CACHE: dict = {"at": 0.0, "value": None}
_PRECHECK_LOCK = threading.Lock()
PRECHECK_TTL = 60  # 초. 새로고침마다 claude 상태를 다시 묻지 않도록


def precheck() -> dict:
    """상태 확인 결과를 60초간 기억. 동시에 여러 번 불려도 한 번만 실제 확인."""
    import time
    with _PRECHECK_LOCK:
        if _PRECHECK_CACHE["value"] is not None and time.time() - _PRECHECK_CACHE["at"] < PRECHECK_TTL:
            return _PRECHECK_CACHE["value"]
        value = _precheck_uncached()
        _PRECHECK_CACHE.update(at=time.time(), value=value)
        return value


def _precheck_uncached() -> dict:
    result = {"skillspector": False, "skillspector_version": "", "rules": RULES_DIR.is_dir(),
              "claude": False, "claude_logged_in": False, "claude_message": ""}
    ss = shutil.which("skillspector")
    if ss:
        cp = _run_quick([ss, "--version"])
        if cp and cp.returncode == 0:
            result["skillspector"] = True
            result["skillspector_version"] = re.sub(r"(?i)^skillspector\s*v?", "",
                                                   cp.stdout.decode("utf-8", "replace").strip())
    cl = shutil.which("claude")
    if not cl:
        result["claude_message"] = "Claude Code가 설치되어 있지 않습니다."
    else:
        result["claude"] = True
        cp = _run_quick([cl, "auth", "status"])
        out = cp.stdout.decode("utf-8", "replace") if cp else ""
        try:
            result["claude_logged_in"] = bool(json.loads(out).get("loggedIn"))
        except (ValueError, AttributeError):
            result["claude_logged_in"] = False
        if not result["claude_logged_in"]:
            result["claude_message"] = "Claude Code 로그인이 필요합니다. 터미널에서 `claude auth login`을 실행하세요."
    return result


# ── 입력 판별 ────────────────────────────────────────────────────────────────
def resolve_input(raw: str) -> tuple[str, str, str | None]:
    """(대상, 종류, 임시폴더) 반환. 종류: url | path | text"""
    text = raw.strip()
    one_line = "\n" not in text
    candidate = text.strip('"').strip("'")  # 탐색기 '경로로 복사'는 따옴표가 붙는다
    if one_line and re.match(r"^https?://", candidate, re.I):
        return candidate, "url", None
    if one_line and len(candidate) < 1024:
        p = Path(candidate).expanduser()
        if p.exists():
            return str(p.resolve()), "path", None
        if re.match(r"^[A-Za-z]:\\|^\\\\|^/|^~", candidate):
            raise ValueError(f"경로를 찾을 수 없습니다: {candidate}")
    if len(text.encode("utf-8")) > MAX_PASTE_BYTES:
        raise ValueError("붙여넣은 본문이 너무 큽니다 (512KB 초과). 폴더 경로나 주소로 넣어주세요.")
    tmp = tempfile.mkdtemp(prefix="as_screener_")
    skill_dir = Path(tmp) / "pasted-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(text + "\n", encoding="utf-8")
    return str(skill_dir), "text", tmp


# ── 검사 실행 ────────────────────────────────────────────────────────────────
def _child_env(llm: bool) -> dict:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["NO_COLOR"] = "1"
    if llm:
        env["SKILLSPECTOR_PROVIDER"] = "claude_cli"
        env.setdefault("SKILLSPECTOR_MAX_LLM_CONCURRENCY", "2")
        env["SKILLSPECTOR_OUTPUT_LANGUAGE"] = "Korean"  # LLM 발견 설명을 한국어로
    else:
        env.pop("SKILLSPECTOR_PROVIDER", None)
    return env


def run_tree(argv: list[str], timeout: int, env: dict, cwd: str | None = None, data: bytes | None = None,
             low_priority: bool = True):
    """subprocess.run 대신 사용. 시간 초과 시 Windows에서는 자식 프로세스까지 통째로 종료한다.
    (uv 도구 실행 파일은 python.exe를 따로 띄우므로, 실행기만 끄면 python.exe가 남아 메모리를 먹는다)"""
    # 폼에서는 PC가 버벅이지 않게 낮은 우선순위(기본). 회귀 테스트는 시간이 들쭉날쭉하지 않게 보통 우선순위로 부른다.
    flags = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0) if (os.name == "nt" and low_priority) else 0
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE if data is not None else None, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env, cwd=cwd, creationflags=flags)
    try:
        out, err = proc.communicate(data, timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        else:
            proc.kill()
        proc.communicate()
        raise
    return subprocess.CompletedProcess(argv, proc.returncode, out, err)


def _timing(t0: float, ss_sec: float) -> dict:
    """검사 시간을 SkillSpector(NVIDIA) 몫과 AS 스크리너 몫으로 나눔."""
    total = time.perf_counter() - t0
    return {"total": round(total, 1), "skillspector": round(ss_sec, 1), "ours": round(max(total - ss_sec, 0.0), 1)}


def run_scan(raw: str, llm: bool) -> dict:
    t0 = time.perf_counter()
    ss_sec = 0.0
    ss = shutil.which("skillspector")
    if not ss:
        return {"state": "fail", "title": "SkillSpector가 설치되어 있지 않습니다",
                "detail": "터미널에서 설치 후 다시 시도하세요: uv tool install --python 3.12 git+https://github.com/NVIDIA/skillspector.git"}
    try:
        target, kind, tmp = resolve_input(raw)
    except ValueError as exc:
        return {"state": "fail", "title": "입력을 확인해 주세요", "detail": str(exc)}
    argv = [ss, "scan", target, "--format", "json"]
    if RULES_DIR.is_dir():
        argv += ["--yara-rules-dir", str(RULES_DIR)]
    if not llm:
        argv.append("--no-llm")
    t_ss = time.perf_counter()
    try:
        cp = run_tree(argv, SCAN_TIMEOUT, _child_env(llm))
    except subprocess.TimeoutExpired:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        return {"state": "fail", "title": "검사 시간 초과",
                "detail": f"SkillSpector가 {SCAN_TIMEOUT // 60}분 안에 끝나지 않았습니다.",
                "timing": _timing(t0, time.perf_counter() - t_ss)}
    ss_sec = time.perf_counter() - t_ss
    try:
        stdout = cp.stdout.decode("utf-8", "replace")
        stderr = cp.stderr.decode("utf-8", "replace")
        try:
            report = json.loads(stdout[stdout.index("{"):])
        except ValueError:
            tail = "\n".join(stderr.strip().splitlines()[-8:])
            return {"state": "fail", "title": "검사 실패", "detail": tail or f"종료 코드 {cp.returncode}",
                    "timing": _timing(t0, ss_sec)}
        fallback = {"text": "붙여넣은 본문", "url": target.rstrip("/").split("/")[-1]}.get(kind, Path(target).name)
        src_root = target if kind in ("path", "text") else None
        result = normalize(report, kind, llm, stderr, fallback, src_root)
        if result["state"] != "fail":
            sid = secrets.token_urlsafe(12)
            with _STORE_LOCK:
                SESSIONS[sid] = {"kind": kind, "raw": raw if kind == "text" else "",
                                 "target": target if kind != "text" else "", "state": result["state"],
                                 "skill": result.get("skill", ""), "score": result.get("score")}
                while len(SESSIONS) > 50:
                    SESSIONS.pop(next(iter(SESSIONS)))
            result["scan_id"] = sid
        result["timing"] = _timing(t0, ss_sec)
        return result
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def _read_source(src_root: str | None, file: str) -> list[str] | None:
    """검사 대상 원본 파일의 줄 목록. 대상 폴더 밖 경로·큰 파일은 읽지 않음."""
    if not src_root:
        return None
    root = Path(src_root).resolve()
    base = root if root.is_dir() else root.parent
    path = (base / file).resolve() if file else root
    if root.is_file() and not file:
        path = root
    try:
        path.relative_to(base)
    except ValueError:
        return None
    if not path.is_file() or path.stat().st_size > 5_000_000:
        return None
    return path.read_text(encoding="utf-8", errors="replace").split("\n")


def source_lines(src_root: str | None, file: str, start, end) -> str:
    """검사 대상 원본에서 걸린 줄만 꺼낸다 (최대 4줄)."""
    if not isinstance(start, int) or start < 1:
        return ""
    lines = _read_source(src_root, file)
    if lines is None:
        return ""
    stop = end if isinstance(end, int) and end >= start else start
    stop = min(stop, start + 3)
    picked = [ln.strip()[:160] for ln in lines[start - 1:stop]]
    return "\n".join(p for p in picked if p)


def fix_line(src_root: str | None, file: str, line, finding: str):
    """우리 규칙이 줄 첫머리 공격을 앞 줄의 줄바꿈부터 잡은 경우 줄 번호를 +1 보정.
    SkillSpector는 일치 시작 위치로 줄을 세므로, 일치 문자열이 줄바꿈으로 시작하면 한 줄 위를 가리킨다.
    finding = 일치 문자열들('; '로 이어짐). 다음 줄이 그 문자열로 시작할 때만 고친다."""
    if not isinstance(line, int) or line < 1 or "\n" not in finding:
        return line
    lines = _read_source(src_root, file)
    if not lines or line >= len(lines):
        return line
    nxt = lines[line].rstrip("\r").lstrip("\ufeff")
    for part in finding.split("; "):
        if part.startswith("\n"):
            head = part[1:].rstrip("\r")[:12]
            if head and nxt.startswith(head):
                return line + 1
    return line


# ── 파일 분류: 에이전트가 읽는 '지침' vs AS 스크리너가 가져오지 않는 '코드·의존성' ──
INSTR_NAMES = {"skill.md", "agents.md", "claude.md", "gemini.md", ".cursorrules", ".windsurfrules",
               "copilot-instructions.md", ".clinerules"}
INSTR_DIRS = (".claude/", ".agents/", ".cursor/", ".windsurf/", ".github/prompts/", ".clinerules/",
              "skills/", "commands/", "agents/", "prompts/", "rules/")
DOC_NAMES = {"readme.md", "changelog.md", "license.md", "contributing.md", "security.md",
             "code_of_conduct.md", "readme.txt", "license", "license.txt"}
TEXT_EXT = (".md", ".mdc", ".txt", ".markdown")
LLM_IDS = ("SDI", "SQP", "SSD")


def is_instruction(file: str, rid: str, kind: str, skill_root: bool) -> bool:
    """이 발견이 에이전트가 읽는 지침 파일에서 나왔는가."""
    if kind == "text" or rid.upper().startswith(LLM_IDS):
        return True
    f = re.sub(r"^(\./)+", "", (file or "").replace("\\", "/")).lower()
    name = f.rsplit("/", 1)[-1]
    if name in DOC_NAMES or name.startswith("readme"):
        return False
    if name in INSTR_NAMES:
        return True
    if not name.endswith(TEXT_EXT):
        return False  # 스크립트·설정·의존성 → 가져오지 않음
    if any(d in "/" + f for d in ("/" + x for x in INSTR_DIRS)) or f.startswith(INSTR_DIRS):
        return True
    return skill_root  # 스킬 폴더 자체를 검사했다면 그 안의 문서는 모두 지침(참고 문서 포함)


SEV_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}


def normalize(report: dict, kind: str, llm: bool, stderr: str, fallback_name: str = "",
              src_root: str | None = None) -> dict:
    ra = report.get("risk_assessment", {})
    comp = report.get("analysis_completeness", {}) or {}
    rec = str(ra.get("recommendation", "CAUTION")).upper()
    status = str(comp.get("status", "complete"))
    coverage = comp.get("coverage_percent")
    degraded = "Degraded scan" in stderr or "LLM batch failed" in stderr
    failed = (not report.get("execution_successful", True)) or status == "failed" or (llm and degraded)

    skill_root = str((report.get("skill") or {}).get("name") or "unknown") != "unknown"
    issues = []
    for it in report.get("issues", []):
        rid = str(it.get("id", ""))
        expl = str(it.get("explanation") or it.get("finding") or "")
        haystack = " ".join(str(it.get(k) or "") for k in ("explanation", "finding", "pattern", "message"))
        m = re.search(r"YARA rule '([^']+)'", haystack) or re.search(r"\b((?:ko|zh|ja)_[a-z_]+)\b", haystack)
        yrule = m.group(1) if m else ""
        ours = OUR_PREFIX.get(yrule[:3], "")
        if yrule in KO_RULES:
            title, desc = KO_RULES[yrule]
            cat = ours
        elif ours:
            km = re.search(r"\[(?:KO|ZH|JA)\]\s*([^\[]+)", haystack)
            title, desc, cat = ours, (km.group(1).strip() if km else yrule), ours
        else:
            title, desc, cat = ko_category(rid), expl, ko_category(rid)
            if yrule:
                title = f"악성 패턴 ({yrule})"
        loc = it.get("location", {}) or {}
        line = loc.get("start_line")
        if ours:
            line = fix_line(src_root, str(loc.get("file") or ""), line, str(it.get("finding") or ""))
        end = loc.get("end_line")
        where = f"{loc.get('file', '')}:{line}" + (f"–{end}" if end and end != line else "") if line else str(loc.get("file", ""))
        group = "instr" if is_instruction(str(loc.get("file") or ""), rid, kind, skill_root) else "code"
        issues.append({"group": group, "severity": str(it.get("severity", "")).upper(), "id": rid, "title": title,
                       "category": cat, "desc": desc, "where": where,
                       "snippet": source_lines(src_root, str(loc.get("file") or ""), line, end)
                                  or clean_snippet(str(it.get("code_snippet") or "")),
                       "confidence": it.get("confidence")})
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
    issues.sort(key=lambda x: order.get(x["severity"], 9))

    instr = [i for i in issues if i["group"] == "instr"]
    code = [i for i in issues if i["group"] == "code"]
    instr_max = max((SEV_RANK.get(i["severity"], 0) for i in instr), default=-1)
    code_max = max((SEV_RANK.get(i["severity"], 0) for i in code), default=-1)
    code_note = ""
    if code:
        code_note = (f"코드·의존성 쪽 발견 {len(code)}건은 AS 스크리너가 가져오지 않는 파일이라 판정에서 뺐습니다."
                     + (" 그중 치명 항목이 있어 원본을 그대로 설치하면 위험합니다." if code_max >= 4 else ""))
    if failed:
        state, title = "fail", "검사 실패 · 다시 시도 필요"
        detail = ("LLM 정밀검사가 실행되지 않았습니다. Claude Code 로그인 상태를 확인하세요."
                  if llm and degraded else "검사가 끝까지 수행되지 않았습니다. 아래 결과는 일부만 반영됐습니다.")
    elif instr_max >= 3:
        state, title, detail = "block", "차단 · 설치하지 마세요", "에이전트 지침에서 위험한 지시가 발견됐습니다."
    elif instr_max == 2 or code_max >= 4:
        state, title = "caution", "주의 · 기본 차단"
        detail = ("에이전트 지침에 확인이 필요한 항목이 있습니다. 내용을 보고 판단하세요."
                  if instr_max == 2 else "지침은 깨끗하지만 원본 코드에 치명 항목이 있습니다. 지침만 새로 쓰는 방식으로 가져오세요.")
    else:
        state, title, detail = "pass", "통과 · 에이전트 지침 기준", "에이전트 지침에서 위험한 지시가 발견되지 않았습니다."
    if state == "pass" and not llm:
        detail += " 처음 보는 스킬이면 LLM 정밀검사도 권장합니다."
    return {"state": state, "title": title, "detail": detail, "score": ra.get("score"),
            "skill": _skill_name(report, fallback_name), "kind": kind, "llm": llm,
            "coverage": coverage, "issues": issues, "code_note": code_note,
            "instr_count": len(instr), "code_count": len(code)}


def _skill_name(report: dict, fallback: str) -> str:
    name = str((report.get("skill") or {}).get("name") or "")
    if name and name != "unknown":
        return name
    return f"{fallback} (SKILL.md 없음 · 스킬 폴더가 아닐 수 있음)" if fallback else "알 수 없음"


# ── 재작성 · 자동 검증 · 승인 ────────────────────────────────────────────────
JOBS: dict = {}
MAX_ROUNDS = 2  # 자동 재작성 최대 횟수 (Claude 사용량 상한)


def start_rewrite(scan_id: str, lang: str, feedback: str = "") -> dict:
    sess = SESSIONS.get(scan_id)
    if not sess:
        return {"ok": False, "error": "검사 기록이 없습니다. 다시 검사한 뒤 재작성하세요."}
    if sess["state"] == "block":
        return {"ok": False, "error": "차단된 스킬은 재작성하지 않습니다. 위험한 지시가 의도에 섞여 있을 수 있습니다."}
    jid = secrets.token_urlsafe(12)
    job = {"status": "running", "step": "준비 중", "log": [], "result": None}
    with _STORE_LOCK:
        JOBS[jid] = job
        while len(JOBS) > 20:
            JOBS.pop(next(iter(JOBS)))
    threading.Thread(target=_rewrite_job, args=(job, sess, "en" if lang == "en" else "ko", feedback[:3000]),
                     daemon=True).start()
    return {"ok": True, "job_id": jid}


def _step(job: dict, text: str) -> None:
    job["step"] = text
    job["log"].append(text)


def _rescan_check(new_dir: Path, llm: bool) -> dict:
    r = run_scan(str(new_dir), llm)
    with _STORE_LOCK:
        for k in [k for k, v in SESSIONS.items() if v.get("target") == str(new_dir)]:
            SESSIONS.pop(k, None)
    name = "LLM 재검사" if llm else "정적 재검사"
    st = r.get("state")
    instr = [i for i in r.get("issues", []) if i.get("group") != "code"]
    detail = r.get("title", "") + (" · " + "; ".join(f"{i['title']}({i['where']})" for i in instr[:4]) if instr else "")
    if st == "fail":
        status = "warn" if llm else "fail"
        detail = "검사를 끝까지 못 함: " + r.get("detail", "")
    else:
        status = {"pass": "pass", "caution": "warn", "block": "fail"}.get(st, "warn")
    return {"id": "llm" if llm else "static", "name": name, "status": status, "detail": detail}


def _rewrite_job(job: dict, sess: dict, lang: str, first_feedback: str = "") -> None:
    work = Path(tempfile.mkdtemp(prefix="as_rewrite_"))
    try:
        _step(job, "원본 가져오는 중")
        if sess["kind"] == "text":
            root = work / "src"
            root.mkdir()
            (root / "SKILL.md").write_text(sess["raw"] + "\n", encoding="utf-8")
        elif sess["kind"] == "url":
            root = rw.fetch_github(sess["target"], work)
        else:
            root = Path(sess["target"])
            root = root.parent if root.is_file() else root
        if not (root / "SKILL.md").is_file():
            dirs = rw.find_skill_dirs(root)
            hint = (" 이 안에서 찾은 스킬 폴더: " + ", ".join(dirs[:8])) if dirs else ""
            raise rw.RewriteError("SKILL.md가 있는 스킬 폴더만 재작성할 수 있습니다." + hint)
        _step(job, "① 실행 파일 제거")
        keep, drop, lic = rw.classify(root)
        license_text = rw.find_license(root, work)
        if license_text and not lic:
            lic = license_text.strip().splitlines()[0][:120]
        if not any(f["path"] == "SKILL.md" for f in keep):
            raise rw.RewriteError("SKILL.md를 읽을 수 없습니다 (너무 크거나 형식 문제).")
        originals = {f["path"]: (root / f["path"]).read_text(encoding="utf-8", errors="replace") for f in keep}
        original_sha = rw.sha256_files(root, keep)

        rounds, feedback, files, report, checks = [], first_feedback, {}, "", []
        for rnd in range(1, MAX_ROUNDS + 1):
            _step(job, f"② {rnd}차 재작성 중 (Claude)")
            files, report = rw.parse_output(rw.run_claude(rw.build_prompt(root, keep, drop, lang, feedback)))
            name = rw.skill_name(files, sess.get("skill") or "rewritten-skill")
            new_dir = work / f"round{rnd}" / name
            new_dir.mkdir(parents=True)
            rw.write_files(new_dir, files)
            _step(job, f"③ {rnd}차 자동 검증: 형식·새 위험 요소·복사율")
            checks = [rw.check_format(files), rw.check_new_risks(originals, files), rw.check_copy(originals, files)]
            _step(job, f"③ {rnd}차 자동 검증: 정적 재검사")
            checks.append(_rescan_check(new_dir, False))
            _step(job, f"③ {rnd}차 자동 검증: LLM 재검사 (Claude)")
            checks.append(_rescan_check(new_dir, True))
            _step(job, f"③ {rnd}차 자동 검증: 의도 보존 독립 검토 (별도 Claude)")
            checks.append(rw.check_fidelity(originals, files))
            fails = [c for c in checks if c["status"] == "fail"]
            rounds.append({"round": rnd, "fails": [f"{c['name']}: {c['detail']}" for c in fails]})
            if not fails:
                break
            feedback = rw.feedback_from(checks)
            if rnd < MAX_ROUNDS:
                _step(job, f"{rnd}차 검증 실패 {len(fails)}건 → 문제점을 알려주고 다시 작성")

        passed = sum(c["status"] == "pass" for c in checks)
        ok_to_approve = not any(c["status"] == "fail" for c in checks)
        rid = secrets.token_urlsafe(12)
        prov = {"tool": f"AS 스크리너 v{VERSION}", "source": sess["target"] or "붙여넣은 본문",
                "source_kind": sess["kind"], "source_license": lic, "source_files_sha256": original_sha,
                "original_verdict": sess["state"], "original_score": sess.get("score"),
                "removed_files": drop, "rewrite_report": report, "auto_checks": checks, "rounds": rounds,
                "rewritten_at": __import__("datetime").datetime.now().isoformat(timespec="seconds")}
        with _STORE_LOCK:
            REWRITES[rid] = {"files": files, "name": name, "prov": prov, "ok": ok_to_approve,
                             "license_text": license_text}
            while len(REWRITES) > 20:
                REWRITES.pop(next(iter(REWRITES)))
        job["result"] = {"ok": True, "rewrite_id": rid, "name": name, "kept": keep, "removed": drop,
                         "license": lic, "has_license": bool(license_text), "files": files,
                         "originals": {k: v[:30000] for k, v in originals.items()}, "report": report,
                         "checks": checks, "rounds": rounds, "passed": passed, "total": len(checks),
                         "ok_to_approve": ok_to_approve}
        _step(job, "완료")
    except rw.RewriteError as exc:
        job["result"] = {"ok": False, "error": str(exc)}
    except OSError as exc:
        job["result"] = {"ok": False, "error": f"파일 처리 중 오류: {exc}"}
    except Exception as exc:  # noqa: BLE001  작업 스레드가 조용히 죽지 않게
        job["result"] = {"ok": False, "error": f"예상하지 못한 오류: {exc}"}
    finally:
        job["status"] = "done"
        shutil.rmtree(work, ignore_errors=True)


def do_approve(rewrite_id: str, name: str) -> dict:
    item = REWRITES.get(rewrite_id)
    if not item:
        return {"ok": False, "error": "재작성 기록이 없습니다. 다시 재작성하세요."}
    if not item.get("ok"):
        return {"ok": False, "error": "자동 검증을 통과하지 못해 저장할 수 없습니다."}
    try:
        dest = rw.approve(BASE_DIR, name or item["name"], item["files"], item["prov"], item.get("license_text", ""))
    except OSError as exc:
        return {"ok": False, "error": f"저장 실패: {exc}"}
    return {"ok": True, "path": str(dest), "name": dest.name}


# ── 설치 관리 ────────────────────────────────────────────────────────────────
def do_skills() -> dict:
    try:
        return {"ok": True, "skills": ins.list_skills(BASE_DIR),
                "targets": {t: {"label": lbl, "path": str(ins.target_dir(t))} for t, (lbl, _) in ins.TARGETS.items()}}
    except OSError as exc:
        return {"ok": False, "error": f"목록을 읽지 못했습니다: {exc}"}


def do_install(body: dict, remove: bool = False) -> dict:
    name, target = str(body.get("name", "")), str(body.get("target", "claude"))
    try:
        if remove:
            dest = ins.uninstall(name, target)
        else:
            dest = ins.install(BASE_DIR, name, target, overwrite=bool(body.get("overwrite")))
    except ins.InstallError as exc:
        return {"ok": False, "code": exc.code, "error": str(exc)}
    except OSError as exc:
        return {"ok": False, "code": "os", "error": f"파일 작업 실패: {exc}"}
    return {"ok": True, "path": str(dest)}


# ── 웹 서버 ──────────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    server_version = "ASScreener/" + VERSION

    def log_message(self, fmt, *args):  # 조용히
        pass

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _send(self, code: int, body: bytes, ctype: str):
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass  # 브라우저가 먼저 탭을 닫거나 새로고침함 → 무시

    def _json(self, code: int, obj: dict):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _authorized(self) -> bool:
        return self._host_ok() and secrets.compare_digest(self.headers.get("X-AS-Token", ""), TOKEN)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, b"forbidden", "text/plain")
        if self.path == "/":
            html = PAGE.replace("__TOKEN__", TOKEN).replace("__VERSION__", VERSION)
            return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
        if self.path.startswith("/api/job?id="):
            if not self._authorized():
                return self._json(403, {"error": "forbidden"})
            job = JOBS.get(self.path.split("=", 1)[1])
            if not job:
                return self._json(200, {"status": "done", "result": {"ok": False, "error": "작업 기록이 없습니다."}})
            return self._json(200, {"status": job["status"], "step": job["step"], "log": job["log"],
                                    "result": job["result"] if job["status"] == "done" else None})
        if self.path == "/api/precheck":
            if not self._authorized():
                return self._json(403, {"error": "forbidden"})
            return self._json(200, precheck())
        if self.path == "/api/skills":
            if not self._authorized():
                return self._json(403, {"error": "forbidden"})
            return self._json(200, do_skills())
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if self.path not in ("/api/scan", "/api/rewrite", "/api/approve", "/api/install", "/api/uninstall") \
                or not self._authorized():
            return self._json(403, {"error": "forbidden"})
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_PASTE_BYTES * 2:
            return self._json(400, {"state": "fail", "title": "입력이 비었거나 너무 큽니다", "detail": ""})
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except ValueError:
            return self._json(400, {"state": "fail", "title": "잘못된 요청", "detail": ""})
        if self.path == "/api/rewrite":
            return self._json(200, start_rewrite(str(body.get("scan_id", "")), str(body.get("lang", "ko")),
                                                 str(body.get("feedback", ""))))
        if self.path == "/api/approve":
            return self._json(200, do_approve(str(body.get("rewrite_id", "")), str(body.get("name", ""))))
        if self.path in ("/api/install", "/api/uninstall"):
            if not isinstance(body, dict):
                return self._json(400, {"ok": False, "error": "잘못된 요청"})
            return self._json(200, do_install(body, remove=self.path == "/api/uninstall"))
        raw = str(body.get("input", ""))
        if not raw.strip():
            return self._json(400, {"state": "fail", "title": "검사할 내용을 붙여넣어 주세요", "detail": ""})
        self._json(200, run_scan(raw, bool(body.get("llm"))))


class QuietServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
            return  # 연결 끊김은 정상 상황, 화면에 오류 출력 안 함
        super().handle_error(request, client_address)


PAGE = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AS 스크리너</title>
<style>
:root{--bg:#f6f5f2;--card:#fff;--ink:#1c1b19;--sub:#6b6862;--line:#e3e0d9;--accent:#2f5d50;
--pass:#2e7d4f;--pass-bg:#e8f4ec;--block:#b3261e;--block-bg:#fbeaea;--caution:#a15c00;--caution-bg:#fdf1de;--fail:#5b5b66;--fail-bg:#ececf1}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--card:#1f1f1c;--ink:#ecebe7;--sub:#a3a09a;--line:#34332f;--accent:#7fbfa9;
--pass:#7fd39c;--pass-bg:#1d2f23;--block:#ff8a80;--block-bg:#3a1e1c;--caution:#f0b862;--caution-bg:#3a2c16;--fail:#b9b9c4;--fail-bg:#2a2a30}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 "Pretendard","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif}
.wrap{max-width:920px;margin:0 auto;padding:28px 16px 60px}
header{display:flex;align-items:baseline;gap:12px;margin-bottom:18px}
h1{font-size:22px;margin:0;letter-spacing:-.02em}h1 b{color:var(--accent)}
.ver{color:var(--sub);font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}
textarea{width:100%;min-height:150px;resize:vertical;border:1px solid var(--line);border-radius:10px;padding:12px;font:14px/1.5 ui-monospace,Consolas,monospace;background:var(--bg);color:var(--ink)}
textarea:focus{outline:2px solid var(--accent);outline-offset:1px}
.hint{color:var(--sub);font-size:13px;margin:8px 0 14px}
.row{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between}
label.llm{display:flex;gap:8px;align-items:flex-start;font-size:14px;cursor:pointer;max-width:560px}
label.llm small{display:block;color:var(--sub)}
button{background:var(--accent);color:#fff;border:0;border-radius:10px;padding:11px 22px;font-size:15px;font-weight:600;cursor:pointer}
button:disabled{opacity:.5;cursor:default}
.status{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px;font-size:12.5px}
.pill{border:1px solid var(--line);border-radius:999px;padding:3px 10px;color:var(--sub)}
.pill.ok::before{content:"● ";color:var(--pass)}.pill.no::before{content:"● ";color:var(--block)}
#result{margin-top:18px}
.verdict{border-radius:14px;padding:18px 20px;display:flex;gap:18px;align-items:center;flex-wrap:wrap}
.verdict .big{font-size:21px;font-weight:700}
.verdict .score{margin-left:auto;text-align:right;font-variant-numeric:tabular-nums}
.verdict .score b{font-size:28px}
.pass{background:var(--pass-bg);color:var(--pass)}.block{background:var(--block-bg);color:var(--block)}
.caution{background:var(--caution-bg);color:var(--caution)}.fail{background:var(--fail-bg);color:var(--fail)}
.verdict p{margin:2px 0 0;color:var(--ink);opacity:.85;font-size:14px}
.meta{color:var(--sub);font-size:13px;margin:10px 2px}
table{width:100%;border-collapse:collapse;margin-top:6px;font-size:14px}
th,td{text-align:left;padding:10px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--sub);font-weight:600;font-size:12.5px;white-space:nowrap}
.sev{font-weight:700;font-size:12.5px;white-space:nowrap}
.sev.CRITICAL{color:var(--block)}.sev.HIGH{color:var(--block)}.sev.MEDIUM{color:var(--caution)}.sev.LOW,.sev.INFO{color:var(--sub)}
td .t{font-weight:600}td .d{color:var(--sub);font-size:13px;margin-top:2px}
code.snip{display:block;margin-top:6px;white-space:pre-wrap;word-break:break-all;font-size:12px;background:var(--bg);border-radius:6px;padding:6px 8px;color:var(--ink)}
.where{font:12px ui-monospace,Consolas,monospace;color:var(--sub);white-space:nowrap}
h2.sec{font-size:15px;margin:22px 2px 8px}h2.sec span{color:var(--sub);font-weight:500;font-size:13px;margin-left:6px}
.card.empty{color:var(--sub);font-size:14px}
details.codegrp{margin-top:16px}details.codegrp summary{cursor:pointer;color:var(--sub);font-size:14px;padding:8px 2px}
details.codegrp summary b{color:var(--ink)}
.next select{border:1px solid var(--line);border-radius:8px;padding:8px;background:var(--card);color:var(--ink)}
.files{font-size:13px;padding:10px 14px}.frow{padding:3px 0}.frow code{font-size:12.5px}
.frow.keep{color:var(--pass)}.frow.drop{color:var(--sub)}.frow.drop span{margin-left:6px;font-size:12px}.frow.lic{color:var(--caution);margin-top:4px}
pre.report{white-space:pre-wrap;margin:0;font:13.5px/1.6 inherit;font-family:inherit}
details.cmp{margin-top:10px}details.cmp summary{cursor:pointer;padding:6px 2px;color:var(--sub)}details.cmp summary b{color:var(--ink)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:10px}
pre.doc{white-space:pre-wrap;word-break:break-word;max-height:460px;overflow:auto;margin:0;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:var(--card);font:12.5px/1.55 ui-monospace,Consolas,monospace}
.lbl{font-size:12px;color:var(--sub);margin:2px 2px 4px}.lbl.new{color:var(--pass);font-weight:600}
.approve{display:flex;flex-wrap:wrap;gap:12px;align-items:center}.approve input{border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin-left:6px;background:var(--bg);color:var(--ink);font:14px ui-monospace,Consolas,monospace}
#apout{flex-basis:100%;margin:0}.lic-note{flex-basis:100%;font-size:13px;color:var(--sub);background:var(--bg);border-radius:8px;padding:8px 10px}.lic-note.nolic{color:var(--caution);background:var(--caution-bg)}
button.ghost{background:transparent;color:var(--accent);border:1px solid var(--accent)}.okmsg{color:var(--pass)}
@media (max-width:640px){.two{grid-template-columns:1fr}}
.checks{padding:6px 14px}.chk{display:flex;gap:12px;padding:9px 0;border-bottom:1px solid var(--line)}.chk:last-child{border-bottom:0}
.chk .ic{width:22px;height:22px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;flex:none}
.chk.c-pass .ic{background:var(--pass-bg);color:var(--pass)}.chk.c-warn .ic{background:var(--caution-bg);color:var(--caution)}
.chk.c-fail .ic{background:var(--block-bg);color:var(--block)}.chk.c-skip .ic{background:var(--fail-bg);color:var(--fail)}
.chk.c-fail b{color:var(--block)}.chk.c-warn b{color:var(--caution)}
.chk .d{color:var(--sub);font-size:13px}
details.more{margin-top:18px}details.more>summary{cursor:pointer;color:var(--sub);font-size:14px;padding:8px 2px}
ol.steps{margin:8px 0 0;padding-left:20px;color:var(--sub);font-size:13px}ol.steps li::marker{color:var(--pass)}
.next{margin-top:16px;display:flex;gap:10px;align-items:center;color:var(--sub);font-size:13px;flex-wrap:wrap}
.next button:disabled{background:transparent;color:var(--sub);border:1px dashed var(--line)}
.spin{display:inline-block;width:14px;height:14px;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;animation:r .8s linear infinite;vertical-align:-2px;margin-right:6px}
@keyframes r{to{transform:rotate(360deg)}}
details.mine{margin-top:14px}details.mine>summary{cursor:pointer;font-size:14px;padding:6px 2px;color:var(--sub)}details.mine>summary b{color:var(--ink)}
.st{display:inline-block;font-size:12px;font-weight:600;border-radius:999px;padding:1px 9px;white-space:nowrap}
.st.installed{background:var(--pass-bg);color:var(--pass)}.st.none{background:var(--bg);color:var(--sub)}
.st.modified,.st.tampered{background:var(--block-bg);color:var(--block)}.st.foreign{background:var(--caution-bg);color:var(--caution)}
button.sm{padding:4px 11px;font-size:12.5px;border-radius:8px;margin:4px 4px 0 0;font-weight:600}
button.danger{background:transparent;color:var(--block);border:1px solid var(--block)}
td .prob{color:var(--block);font-size:12px;margin-top:3px}td .src{font:12px ui-monospace,Consolas,monospace;color:var(--sub);word-break:break-all}
.msg{font-size:13px;margin-top:8px;white-space:pre-wrap}.msg.err{color:var(--block)}.msg.ok{color:var(--pass)}
@media (max-width:640px){td.where-col,th.where-col{display:none}.verdict .score{margin-left:0;text-align:left}}
</style></head><body><div class="wrap">
<header><h1><b>AS</b> 스크리너</h1><span class="ver">에이전트·스킬 검사 · 시제품 v__VERSION__</span></header>
<div class="card">
<textarea id="inp" placeholder="여기에 붙여넣기&#10;&#10;· 깃허브 주소   https://github.com/사용자/저장소/tree/main/skills/이름&#10;· 폴더 경로     D:\다운로드\some-skill&#10;· SKILL.md 본문 전체"></textarea>
<div class="hint">스킬 코드는 실행하지 않고 읽기만 합니다. 깃허브는 저장소 전체보다 스킬 폴더 주소가 빠릅니다.</div>
<div class="row">
<label class="llm"><input type="checkbox" id="llm"><span>LLM 정밀검사도 하기<small id="llmnote">영어 외 언어·교묘한 지시까지 잡습니다. Claude 사용량이 들고 30~60초 걸립니다.</small></span></label>
<button id="go">검사하기</button></div>
<div class="status" id="status"><span class="pill">상태 확인 중…</span></div>
</div>
<details class="mine" id="mine"><summary><b>내 스킬</b> <span id="minecount">승인된 스킬 확인 중…</span></summary>
<div class="card" style="padding:6px 14px" id="minebox"></div><div class="msg" id="minemsg"></div></details>
<div id="result"></div>
</div>
<script>
const TOKEN="__TOKEN__";
const $=s=>document.querySelector(s);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const SEV={CRITICAL:"치명",HIGH:"높음",MEDIUM:"중간",LOW:"낮음",INFO:"참고"};
async function api(path,opt={}){opt.headers=Object.assign({"X-AS-Token":TOKEN,"Content-Type":"application/json"},opt.headers||{});
 const r=await fetch(path,opt);return r.json();}
async function pre(){try{const p=await api("/api/precheck");
 const pills=[[p.skillspector,p.skillspector?"SkillSpector "+p.skillspector_version:"SkillSpector 미설치"],
  [p.rules,p.rules?"한국어·중국어·일본어 규칙 적용":"우리 규칙 없음"],
  [p.claude&&p.claude_logged_in,p.claude_logged_in?"Claude 로그인됨 (LLM 가능)":(p.claude?"Claude 로그인 필요":"Claude Code 미설치")]];
 $("#status").innerHTML=pills.map(([ok,t])=>`<span class="pill ${ok?"ok":"no"}">${esc(t)}</span>`).join("");
 if(!(p.claude&&p.claude_logged_in)){$("#llm").disabled=true;$("#llmnote").textContent=p.claude_message+" (1차 검사는 그대로 가능)";}
 if(!p.skillspector){$("#go").disabled=true;}
}catch(e){$("#status").innerHTML='<span class="pill no">서버 연결 실패</span>';}}
function table(list){let t=`<table><thead><tr><th>심각도</th><th>발견 내용</th><th class="where-col">위치</th></tr></thead><tbody>`;
  for(const i of list){t+=`<tr><td><span class="sev ${esc(i.severity)}">${esc(SEV[i.severity]||i.severity)}</span></td>
   <td><div class="t">${esc(i.title)} <span class="where">${esc(i.id)}</span></div><div class="d">${esc(i.desc)}</div>${i.snippet?`<code class="snip">${esc(i.snippet)}</code>`:""}</td>
   <td class="where where-col">${esc(i.where)}</td></tr>`;}
  return t+`</tbody></table>`;}
function timingLine(t){if(!t)return "";
 // 표시 단위로 먼저 반올림하고 AS 스크리너 몫은 '총 - SkillSpector'로 계산 → 항상 더하면 총이 맞음
 const d=t.total<10?1:0, T=+t.total.toFixed(d), S=Math.min(+t.skillspector.toFixed(d),T), O=(T-S).toFixed(d);
 let h=`<div class="meta">검사 시간 ${T.toFixed(d)}초 — <b>SkillSpector(NVIDIA) ${S.toFixed(d)}초</b> · AS 스크리너 ${O}초</div>`;
 if(t.skillspector>=60) h+=`<div class="hint">SkillSpector는 PC가 멈추지 않도록 낮은 우선순위로 돌립니다. 다른 작업을 하고 있으면 더 오래 걸립니다.</div>`;
 return h;}
function render(r){
 const icon={pass:"✓",block:"✕",caution:"!",fail:"?"}[r.state]||"";
 let h=`<div class="verdict ${r.state}"><div><div class="big">${icon} ${esc(r.title)}</div><p>${esc(r.detail)}</p></div>`;
 if(r.score!=null) h+=`<div class="score">원본 그대로 설치 시<br><b>${esc(r.score)}</b>/100</div>`;
 h+=`</div>`;
 const kind={url:"깃허브·웹 주소",path:"폴더 경로",text:"붙여넣은 본문"}[r.kind]||"";
 if(r.skill||kind) h+=`<div class="meta">${esc(r.skill?"스킬: "+r.skill+" · ":"")}${esc(kind)} · ${r.llm?"1차 + LLM 정밀검사":"1차 검사(정적 + 한국어·중국어·일본어 규칙)"}${r.coverage!=null?" · 검사 범위 "+esc(Math.round(r.coverage))+"%":""}</div>`;
 const instr=(r.issues||[]).filter(i=>i.group!=="code"), code=(r.issues||[]).filter(i=>i.group==="code");
 h+=timingLine(r.timing);
 if(r.state==="fail"&&!(r.issues&&r.issues.length)){$("#result").innerHTML=h;return;}
 h+=`<h2 class="sec">에이전트 지침 <span>판정 기준 · ${instr.length}건</span></h2>`;
 h+= instr.length?`<div class="card" style="padding:6px 14px">${table(instr)}</div>`
   :`<div class="card empty">SKILL.md·명령·규칙 파일에서 위험한 지시가 발견되지 않았습니다.</div>`;
 if(code.length){
  h+=`<details class="codegrp"><summary><b>코드·의존성</b> ${code.length}건 · AS 스크리너가 가져오지 않는 파일 (참고)</summary>
   <p class="hint">${esc(r.code_note)}</p><div class="card" style="padding:6px 14px">${table(code)}</div></details>`;}
 if(r.state==="pass"||r.state==="caution"){
  h+=`<div class="next"><button id="rw">다음: 실행 파일 제거 → 우리 말로 재작성 → 승인</button>
   <select id="lang"><option value="ko">한국어로</option><option value="en">영어로</option></select>
   <span>Claude 사용량이 들고 3~5분 걸립니다 (재작성 + 자동 검증).</span></div>`;
 } else if(r.state==="block"){
  h+=`<div class="next"><button disabled>재작성 불가</button><span>차단된 스킬은 재작성하지 않습니다.</span></div>`;}
 h+=`<div id="rwout"></div>`;
 $("#result").innerHTML=h;
 const b=$("#rw"); if(b) b.onclick=()=>startRewrite(r.scan_id);}
let LAST_SID=null;
async function startRewrite(sid,feedback){
 LAST_SID=sid; $("#rw").disabled=true;
 const box=(steps,cur)=>`<div class="verdict fail progress" style="margin-top:14px"><div><div class="big"><span class="spin"></span>${esc(cur)}</div>
  <p>원문은 데이터로만 읽고 도구 없이 새로 씁니다. 자동 검증 6가지를 통과해야 승인 요청이 나옵니다. (보통 3~5분)</p>
  <ol class="steps">${steps.slice(0,-1).map(t=>`<li>${esc(t)}</li>`).join("")}</ol></div></div>`;
 $("#rwout").innerHTML=box([],"시작하는 중…");
 let st; try{st=await api("/api/rewrite",{method:"POST",body:JSON.stringify({scan_id:sid,lang:$("#lang").value,feedback:feedback||""})});}
 catch(e){return renderRewrite({ok:false,error:String(e)});}
 if(!st.ok) return renderRewrite(st);
 while(true){
  await new Promise(r=>setTimeout(r,1500));
  let j; try{j=await api("/api/job?id="+encodeURIComponent(st.job_id));}catch(e){continue;}
  if(j.status==="done") return renderRewrite(j.result||{ok:false,error:"결과 없음"});
  $("#rwout").innerHTML=box(j.log||[],j.step||"진행 중");}}
const ICON={pass:"✓",warn:"!",fail:"✕",skip:"–"};
function renderRewrite(d){
 const fid=(d.checks||[]).find(c=>c.id==="fidelity");
 if(!d.ok){$("#rwout").innerHTML=`<div class="verdict fail" style="margin-top:14px"><div><div class="big">? 재작성 실패</div><p>${esc(d.error)}</p></div></div>`;$("#rw").disabled=false;return;}
 const warns=d.checks.filter(c=>c.status==="warn").length;
 let h=`<div class="verdict ${d.ok_to_approve?(warns?"caution":"pass"):"block"}" style="margin-top:14px"><div>
   <div class="big">${d.ok_to_approve?"승인 요청":"승인 불가"} · 자동 검증 ${d.passed}/${d.total} 통과${warns?` (주의 ${warns})`:""}</div>
   <p>${d.rounds.length>1?`1차 시도에서 문제가 발견돼 자동으로 다시 썼습니다 (${d.rounds.length}차까지 진행). `:""}${d.ok_to_approve?"아래 검증 결과를 확인하고 승인하세요.":"자동 재작성 후에도 검증을 통과하지 못했습니다. 이 스킬은 직접 만드는 편이 낫습니다."}</p></div></div>`;
 h+=`<h2 class="sec">자동 검증 <span>${d.rounds.length}차 결과</span></h2><div class="card checks">`;
 for(const c of d.checks) h+=`<div class="chk c-${esc(c.status)}"><span class="ic">${ICON[c.status]||"?"}</span><div><b>${esc(c.name)}</b><div class="d">${esc(c.detail)}</div></div></div>`;
 h+=`</div>`;
 if(d.rounds.length>1) h+=`<div class="hint">이전 시도에서 걸린 문제: ${esc(d.rounds.slice(0,-1).map(r=>r.round+"차 — "+r.fails.join("; ")).join(" / "))}</div>`;
 h+=`<h2 class="sec">④ 승인</h2><div class="card approve"><label>저장할 이름 <input id="aname" value="${esc(d.name)}"></label>
  <button id="ap" ${d.ok_to_approve?"":"disabled"}>승인하고 저장</button>
  ${fid&&fid.status==="warn"?`<button id="fix" class="ghost">빠진 내용 보완해서 다시 쓰기</button>`:""}<div class="lic-note ${d.has_license?"":"nolic"}">${d.has_license?`원본 라이선스: <b>${esc(d.license)}</b> · 원문을 <code>LICENSE.original</code>로 함께 저장합니다. 번역·재작성도 2차 저작물이라 라이선스 조건(저작권 표시 등)을 따라야 합니다.`:`원본 라이선스를 찾지 못했습니다. 재작성·번역도 2차 저작물일 수 있으니 <b>개인 사용만</b> 하고 배포·판매는 하지 마세요.`}</div>
  <div id="apout" class="hint">${d.ok_to_approve?"승인하면 approved 폴더에 출처 기록·검증 결과와 함께 저장됩니다.":"자동 검증을 통과하지 못해 저장할 수 없습니다."}</div></div>`;
 h+=`<details class="more"><summary>자세히 보기 — 버린 파일 ${d.removed.length}개 · 재작성 보고 · 원본과 새 버전 비교</summary>`;
 h+=`<h2 class="sec">① 실행 파일 제거 <span>가져온 지침 ${d.kept.length}개 · 버린 파일 ${d.removed.length}개</span></h2><div class="card files">`;
 h+=d.kept.map(f=>`<div class="frow keep">가져옴 <code>${esc(f.path)}</code></div>`).join("");
 h+=d.removed.slice(0,40).map(f=>`<div class="frow drop">버림 <code>${esc(f.path)}</code> <span>${esc(f.reason)}</span></div>`).join("");
 if(d.removed.length>40) h+=`<div class="frow drop">… 외 ${d.removed.length-40}개</div>`;
 if(d.license) h+=`<div class="frow lic">원본 라이선스: ${esc(d.license)}</div>`;
 h+=`</div><h2 class="sec">② 우리 말로 재작성 <span>원문 복사 없이 의도만</span></h2>`;
 if(d.report) h+=`<div class="card"><pre class="report">${esc(d.report)}</pre></div>`;
 for(const [path,txt] of Object.entries(d.files)){
  const orig=d.originals[path];
  h+=`<details class="cmp"><summary><b>${esc(path)}</b> ${orig?"원본과 비교":"새로 만든 파일"}</summary><div class="${orig?"two":""}">`;
  if(orig) h+=`<div><div class="lbl">원본</div><pre class="doc">${esc(orig)}</pre></div>`;
  h+=`<div><div class="lbl new">새 버전</div><pre class="doc">${esc(txt)}</pre></div></div></details>`;}
 h+=`</details>`;
 $("#rwout").innerHTML=h;
 const ap=$("#ap"); if(ap) ap.onclick=async()=>{ap.disabled=true;
  const r=await api("/api/approve",{method:"POST",body:JSON.stringify({rewrite_id:d.rewrite_id,name:$("#aname").value})});
  $("#apout").innerHTML=r.ok?`<b class="okmsg">저장 완료</b> <code>${esc(r.path)}</code><br>출처 기록·검증 결과는 <code>AS_SCREENER.json</code>, 원본 라이선스는 <code>LICENSE.original</code>에 있습니다.
   <div style="margin-top:8px"><button class="sm" id="inst">바로 설치 (Claude Code)</button> <span class="hint">나중에 '내 스킬'에서 설치·제거할 수도 있습니다.</span></div><div class="msg" id="instmsg"></div>`:esc(r.error);
  if(!r.ok){ap.disabled=false;return;}
  loadMine();
  $("#inst").onclick=()=>doInstall(r.name,"claude",false,$("#instmsg"),$("#inst"));};
 const fx=$("#fix"); if(fx) fx.onclick=()=>startRewrite(LAST_SID,"Independent reviewer said these legitimate details were lost; restore them all: "+fid.detail);}
const STL={installed:"설치됨",none:"설치 안 됨",modified:"변조됨",foreign:"같은 이름 다른 스킬"};
async function loadMine(){let d;try{d=await api("/api/skills");}catch(e){$("#minecount").textContent="목록을 불러오지 못함";return;}
 if(!d.ok){$("#minecount").textContent=d.error;return;}
 const n=d.skills.length, inst=d.skills.filter(s=>Object.values(s.installs).some(i=>i.state==="installed")).length,
  bad=d.skills.filter(s=>s.integrity!=="ok"||Object.values(s.installs).some(i=>i.state==="modified")).length;
 $("#minecount").textContent=n?`승인 ${n}개 · 설치 ${inst}개${bad?` · 변조 ${bad}개 ⚠`:""}`:"아직 승인된 스킬이 없습니다";
 if(bad) $("#mine").open=true;
 if(!n){$("#minebox").innerHTML=`<div class="hint">검사 → 재작성 → 승인을 마치면 여기에 나타납니다.</div>`;return;}
 const tk=Object.keys(d.targets);
 let h=`<table><thead><tr><th>스킬</th><th>검증</th>${tk.map(t=>`<th title="${esc(d.targets[t].path)}">${esc(d.targets[t].label)}</th>`).join("")}</tr></thead><tbody>`;
 for(const s of d.skills){
  h+=`<tr><td><div class="t">${esc(s.name)}</div><div class="src">${esc(s.source)}</div><div class="d">승인 ${esc((s.approved_at||"").replace("T"," ").slice(0,16))}${s.license?" · "+esc(s.license):""}</div>
   ${s.integrity!=="ok"?`<div class="prob">⚠ 승인본이 바뀜 — 설치 불가, 다시 검사·승인 필요<br>${esc(s.problems.slice(0,3).join(" / "))}</div>`:""}</td>
   <td>${esc(s.checks||"-")}</td>`;
  for(const t of tk){const i=s.installs[t];let b="";
   if(s.integrity==="ok"&&i.state==="none") b=`<button class="sm" data-a="install" data-n="${esc(s.name)}" data-t="${t}">설치</button>`;
   if(s.integrity==="ok"&&i.state==="modified") b=`<button class="sm" data-a="overwrite" data-n="${esc(s.name)}" data-t="${t}">승인본으로 복구</button>`;
   if(i.state==="installed"||i.state==="modified") b+=`<button class="sm danger" data-a="remove" data-n="${esc(s.name)}" data-t="${t}">제거</button>`;
   h+=`<td><span class="st ${esc(i.state)}">${esc(STL[i.state]||i.state)}</span>${i.state==="modified"?`<div class="prob">${esc((i.problems||[]).slice(0,3).join(" / "))}</div>`:""}
    ${i.state==="foreign"?`<div class="d">직접 만든 스킬로 보고 건드리지 않음</div>`:""}<div>${b}</div></td>`;}
  h+=`</tr>`;}
 $("#minebox").innerHTML=h+`</tbody></table>`;
 $("#minebox").querySelectorAll("button[data-a]").forEach(b=>b.onclick=()=>{const a=b.dataset.a;
  if(a==="remove") doRemove(b.dataset.n,b.dataset.t,b); else doInstall(b.dataset.n,b.dataset.t,a==="overwrite",$("#minemsg"),b);});}
async function doInstall(name,target,overwrite,out,btn){btn.disabled=true;out.className="msg";out.textContent="설치 중…";
 const r=await api("/api/install",{method:"POST",body:JSON.stringify({name,target,overwrite})});
 if(r.ok){out.className="msg ok";out.textContent="설치 완료: "+r.path+"\nClaude Code를 새로 열면 이 스킬을 씁니다.";}
 else if(r.code==="exists"){out.className="msg err";out.innerHTML=esc(r.error)+` <button class="sm" id="ow">덮어쓰기</button>`;
  $("#ow").onclick=()=>doInstall(name,target,true,out,$("#ow"));}
 else{out.className="msg err";out.textContent=r.error;btn.disabled=false;}
 loadMine();}
async function doRemove(name,target,btn){
 if(btn.dataset.sure!=="1"){btn.dataset.sure="1";btn.textContent="정말 제거?";setTimeout(()=>{if(btn.isConnected){btn.dataset.sure="";btn.textContent="제거";}},4000);return;}
 btn.disabled=true;const r=await api("/api/uninstall",{method:"POST",body:JSON.stringify({name,target})});
 const out=$("#minemsg");out.className="msg "+(r.ok?"ok":"err");out.textContent=r.ok?"제거 완료: "+r.path:r.error;loadMine();}
$("#go").onclick=async()=>{const input=$("#inp").value;if(!input.trim()){$("#inp").focus();return;}
 const llm=$("#llm").checked;$("#go").disabled=true;
 $("#result").innerHTML=`<div class="verdict fail"><div class="big"><span class="spin"></span>검사 중… ${llm?"(LLM 포함, 최대 1분)":"(몇 초)"}</div></div>`;
 try{render(await api("/api/scan",{method:"POST",body:JSON.stringify({input,llm})}));}
 catch(e){render({state:"fail",title:"서버 응답 없음",detail:String(e)});}
 finally{$("#go").disabled=false;}};
pre();loadMine();
</script></body></html>"""


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        server = QuietServer((HOST, PORT), Handler)
    except OSError:
        print("=" * 60)
        print(f"이미 다른 AS 스크리너가 실행 중입니다 (포트 {PORT}).")
        print("작업 표시줄에서 예전 검은 창을 찾아 닫은 뒤 다시 실행하세요.")
        print("창이 안 보이면 작업 관리자에서 python.exe 를 종료하세요.")
        print("=" * 60)
        return
    url = f"http://{HOST}:{PORT}/"
    print(f"AS 스크리너 v{VERSION} 실행 중: {url}")
    print("이 창을 닫으면 종료됩니다.")
    if os.environ.get("AS_SCREENER_NO_BROWSER") != "1":
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
