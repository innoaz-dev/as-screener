# 규칙 생성기 공통: YARA 문자열을 바이트 이스케이프(\xNN)로 바꿔 쓴다.
# 이유: 규칙 파일 안의 한글·한자·가나가 규칙 자신에게 걸리지 않게 (규칙 파일 자기 검사).
# 사람이 읽는 원본은 이 생성기(.py)다. 실행: python tools/rulegen/ko_gen.py (zh_gen.py, ja_gen.py) → rules/<언어>/ 에 씀
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def write(lang: str, text: str) -> None:
    p = ROOT / "rules" / lang / f"{lang}_agent_skills.yar"
    p.write_bytes(text.encode("utf-8"))
    print("썼음:", p)
def alt(*xs):
    return "(" + "|".join(xs) + ")"


def hexify(rx: str) -> str:
    # 바이트 단위라서 '地?' 는 마지막 1바이트에만 걸린다 → 자동으로 '(地)?' 로 묶는다.
    rx = re.sub(r"([^\x00-\x7f])(?=[?*+{])", r"(\1)", rx)
    out = []
    for ch in rx:
        if ord(ch) < 128:
            out.append(ch)
        else:
            out.append("".join(f"\\x{b:02X}" for b in ch.encode("utf-8")))
    return "".join(out)


def rule(name, desc, cat, sev, conf, strings, guard=None, guarded=(), after=None):
    """strings: [(id, regex)].
    guard: 설명문·부정문 표지 정규식(private). 일치가 이 표지 범위 안에서 시작하면 무시.
    after: 일치 바로 뒤에 오는 부정 표지(일본어 ~しない 등). 일치 끝 근처에서 시작하면 무시.
    guarded: 위 조건을 적용할 문자열 id들 (나머지는 그대로)."""
    lines = [f"        ${k} = /{hexify(v)}/" for k, v in strings]
    cond = "any of them"
    ids = {k for k, _ in strings}
    guarded = tuple(k for k in guarded if k in ids)
    if (guard or after) and guarded:
        conds = []
        if guard:
            lines.append(f"        $zg = /{hexify(guard)}/ private")
            conds.append("not for any j in (1..#zg) : ( @zg[j] <= @[i] and @zg[j] + !zg[j] >= @[i] )")
        if after:
            lines.append(f"        $za = /{hexify(after)}/ private")
            conds.append("not for any j in (1..#za) : ( @za[j] + 3 >= @[i] + ![i] and @za[j] <= @[i] + ![i] + 9 )")
        free = [k for k, _ in strings if k not in guarded]
        g = ", ".join(f"${k}" for k in guarded)
        f = ", ".join(f"${k}" for k in free)
        cond = ((f"any of ({f}) or\n        " if free else "")
                + f"for any of ({g}) : ( for any i in (1..#) : ( " + " and ".join(conds) + " ) )")
    s = "\n".join(lines)
    return (f'rule {name}\n{{\n    meta:\n        description = "{desc}"\n        category = "{cat}"\n'
            f'        severity = "{sev}"\n        confidence = "{conf}"\n    strings:\n{s}\n    condition:\n        {cond}\n}}\n')
