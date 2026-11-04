# AS 스크리너 — 저장소 정보

AI 코딩 도구(Claude Code·Codex·Cursor 등)가 이 저장소에서 작업할 때 읽는 저장소 정보. 사람용 소개는 README.md.

## 무엇인가
외부 에이전트 스킬을 검사(NVIDIA SkillSpector + 한국어·중국어·일본어 YARA 규칙)하고, 실행 파일을 버린 뒤 의도만 우리 말로 재작성해 자동 검증 후 승인하는 로컬 도구. 파이썬 표준 라이브러리만 쓴다.

## 파일 구조
- `as_screener.py` — 로컬 웹 폼(127.0.0.1:8765), 검사·판정·재작성 작업 관리
- `as_rewriter.py` — 재작성 엔진(원본 가져오기, 실행 파일 제거, Claude 재작성, 자동 검증, 승인 저장)
- `as_installer.py` — 승인 스킬 설치·제거(`~/.claude/skills`, `~/.codex/skills`), 변조 감지(승인본 지문 기준)
- `rules/` — 우리 YARA 규칙. SkillSpector에 `rules` 폴더를 통째로 넘김(하위 폴더까지 읽음)
  - `rules/ko/ko_agent_skills.yar` — 한국어 (`ko_` 규칙)
  - `rules/zh/zh_agent_skills.yar` — 중국어 간체 (`zh_` 규칙)
  - `rules/ja/ja_agent_skills.yar` — 일본어 (`ja_` 규칙)
- `test-skills/` — 회귀 테스트용 시험 스킬 (일부는 일부러 넣은 악성 문장 — 절대 설치 금지)
- `tests/` — 회귀 테스트 (`expected.json`이 기대 결과)
- `LICENSE`·`NOTICE` — Apache-2.0, 출처 표기
- `approved/` — 승인된 재작성 스킬 (Git에 올리지 않음)

## 실행
- 폼: `AS스크리너.bat` 더블클릭 (= `uv run --python 3.12 as_screener.py`)
- 필요: `skillspector` (uv tool), LLM 기능은 Claude Code 로그인

## 테스트 (코드·규칙을 바꾼 뒤 PR 전에 반드시)
- `테스트실행.bat` 더블클릭 (= `uv run --python 3.12 tests\run_regression.py`)
- 전부 ✓ 이어야 한다. 기대 결과를 바꿔야 하면 `tests/expected.json`을 고치고 PR에 이유를 적는다.
- 탐지 규칙을 고칠 때는 오탐 시험(공개 한국어·중국어·일본어 스킬 묶음)도 함께 돌린다: `uv run --python 3.12 tests\run_regression.py --corpus <폴더>`

## 배포
- 배포 없음 (로컬 도구). PR 배포 상태는 항상 '배포 안 함'.

## 기여
- 기능·버그는 Issue를 먼저 만들고, PR 본문에 한 일 / 실제로 돌린 테스트와 결과 / 남은 일을 적는다.
- 탐지 우회 같은 보안 문제는 공개 Issue 대신 SECURITY.md 방법으로 알린다.

## 주의
- `test-skills/`의 악성 시험 파일은 지우거나 '고치지' 않는다. 탐지력 확인용이다.
- 검사 대상 스킬의 코드는 실행하지 않는다. Claude 호출은 도구 없이, 원문은 데이터로만 넘긴다.
- YARA 정규식은 바이트 단위다. 한글·한자·가나 뒤에 `?`를 바로 붙이지 말고 `(地)?`처럼 괄호로 묶는다. `[ ]` 안에 한글·한자·전각 부호를 넣지 않는다. 정규식 안의 `/`는 `\/`로 쓴다.
- 우리 규칙은 '문장 첫머리에서 시키는 문장'만 잡는다(부정·인용·설명문 제외). 줄 첫머리 일치는 줄 번호가 1 작게 나오므로 `as_screener.fix_line`이 보정한다.
- 설치 관리는 `AS_SCREENER.json` 표시가 있는 폴더만 덮어쓰기·제거한다. 사용자가 직접 만든 스킬은 건드리지 않는다.
- 설치 관련 테스트는 `AS_SCREENER_HOME`(임시 폴더)으로만 돌린다. 실제 홈 폴더 스킬을 테스트에 쓰지 않는다.
