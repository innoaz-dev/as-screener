# -*- coding: utf-8 -*-
"""
AS 스크리너 - 탐지 규칙 성적표 (공격 문장 탐지율 + 정상 문장 오탐)

실행 (yara-python 이 필요해서 --with 로 붙임):
    uv run --python 3.12 --with yara-python tools\\measure_recall.py            # 연습 세트
    uv run --python 3.12 --with yara-python tools\\measure_recall.py heldout    # 시험 세트 (점수만)
    uv run --python 3.12 --with yara-python tools\\measure_recall.py practice -v # 놓친 문장·오탐 문장 보기

eval/practice.jsonl : 규칙을 고칠 때 보는 연습 세트
eval/heldout.jsonl  : 시험 세트. 문장을 읽거나 이걸 보고 규칙을 고치지 않는다 (점수만 본다). -v 금지.
각 줄: {"id","lang","kind":"attack|benign","category","style","text"}
"""
import collections
import json
import sys
from pathlib import Path

import yara

ROOT = Path(__file__).resolve().parents[1]
CATS = ["override", "conceal", "stealth", "jailbreak", "cred_access", "exfil"]


def main() -> int:
    which = next((a for a in sys.argv[1:] if not a.startswith("-")), "practice")
    verbose = "-v" in sys.argv
    if which == "heldout" and verbose:
        print("시험 세트는 점수만 봅니다 (-v 금지).")
        return 2
    rules = yara.compile(filepaths={f"r{i}": str(p) for i, p in enumerate(sorted((ROOT / "rules").rglob("*.yar")))})
    sev = {}
    rows = [json.loads(l) for l in (ROOT / "eval" / f"{which}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    tab = collections.defaultdict(lambda: [0, 0])
    fp = collections.defaultdict(lambda: [0, 0, 0])   # [오탐, 전체, 차단 단계 오탐]
    for r in rows:
        ms = rules.match(data=("\n" + r["text"] + "\n").encode("utf-8"))
        names = [m.rule for m in ms]
        block = any(m.meta.get("severity") in ("HIGH", "CRITICAL") for m in ms)
        if r["kind"] == "attack":
            k = (r["lang"], r["category"])
            tab[k][1] += 1
            tab[k][0] += bool(names)
            if verbose and not names:
                print("  놓침", r["id"], r["style"], r["text"][:80].replace("\n", "⏎"))
        else:
            fp[r["lang"]][1] += 1
            fp[r["lang"]][0] += bool(names)
            fp[r["lang"]][2] += block
            if verbose and names:
                print("  오탐", r["id"], r["style"], r["text"][:80].replace("\n", "⏎"), names)
    print(f"[{which}] 공격 문장 탐지율 (잡은 수/전체)  |  정상 문장 오탐 (그중 차단 단계)")
    print("언어 " + " ".join(f"{c[:8]:>9}" for c in CATS) + "      합계     |  오탐")
    for lang in ("ko", "zh", "ja"):
        a = sum(tab[(lang, c)][0] for c in CATS)
        b = sum(tab[(lang, c)][1] for c in CATS)
        cells = " ".join(f"{tab[(lang, c)][0]:>4}/{tab[(lang, c)][1]:<4}" for c in CATS)
        f = fp[lang]
        print(f"{lang:4} {cells}  {a:>3}/{b} {a * 100 // max(b, 1):>3}%  |  {f[0]}/{f[1]} ({f[2]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
