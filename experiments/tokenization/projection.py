"""투영: 초안 문법으로 AI 메시지를 쓰면 실제로 몇 토큰이 드는가.

corpus/gloss_1.json, gloss_2.json(두 추정자가 독립적으로 만든 형태소 분석)을
실제 문자열로 바꿔 7개 토크나이저로 잰다. 형태소마다 띄어 쓰는 표기(W2)를 쓰고,
형태소 형태는 "앞 공백 + 형태"의 평균 토큰 수가 가장 적은 것부터 자주 쓰는 형태소에 배정한다.

문법 장치를 하나씩 줄이는 시나리오(누적)
- S0 strict      : 추정자가 적은 그대로 (매 절 화행·확신도·증거성 3개)
- S1 elided      : 기본값(단언·높은 확신·직접 관찰)은 생략
- S2 fused       : 화행·확신도·증거성을 접사 하나로 합치고, 모두 기본값이면 생략
- S3 positional  : 행위자·대상·주제 역할 접사를 빼고 어순으로 나타냄
- S4 no-linker   : 합성어 연결 접사(LNK)와 수식 표지(ATR)를 뺌
- S5 raw-digits  : 숫자를 아라비아 숫자로 그대로 씀 (알파벳 전용 규칙을 완화해야 함)

출력: results/projection.json, results/projection.md
사용법: python3 projection.py
"""

from __future__ import annotations

import itertools
import json
import re
import statistics
import time
from pathlib import Path

from wordfreq import zipf_frequency

from toklib import load_all

HERE = Path(__file__).resolve().parent
VOWELS = "aeiou"
CONSONANTS = "bcdfghjklmnpqrstvwxyz"
WORD_LANGS = ["en", "es", "de", "fr", "it", "pt", "nl", "tr", "id", "pl", "sv"]
SHAPES = ["CV", "CVC", "CCV", "CVCC", "CCVC", "CVCV"]
CONTEXT = "the"  # 앞 문맥. SentencePiece의 가짜 공백을 피하려고 문맥을 붙여 잰다
N_CLOSED = 150  # 접사·표지·숫자·변수(닫힌 부류)에 먼저 주는 가장 싼 형태 수
ROOT_LEXICON = 1000  # 가정한 핵심 어근 수
SCENARIOS = ["S0_strict", "S1_elided", "S2_fused", "S3_positional", "S4_no_linker", "S5_raw_digits"]

# 추정자별 표지 이름 (두 추정자는 이름표를 다르게 붙였다)
PRAG = {
    1: {"act": lambda a: a.startswith("SA."), "default": {"SA.assert", "CF.high", "EV.observed"},
        "member": lambda a: a.startswith(("SA.", "CF.", "EV."))},
    2: {"act": lambda a: a.rstrip("*") in {"ASRT", "CMD", "QUES", "PROP", "REQ"},
        "default": {"ASRT*", "HIGH*", "OBS*"},
        "member": lambda a: a.rstrip("*") in {"ASRT", "CMD", "QUES", "PROP", "REQ", "HIGH", "LOW", "CERT", "OBS",
                                              "TOOL", "USR", "INF"}},
}
CORE_ROLES = {"AGT", "PAT", "THM"}
LINKERS = {"LNK", "ATR"}


def shape_forms(shape: str) -> list[str]:
    pools = [CONSONANTS if ch == "C" else VOWELS for ch in shape]
    return ["".join(p) for p in itertools.product(*pools)]


def form_costs(toks: dict) -> list[dict]:
    """후보 형태마다 토크나이저별 토큰 수(앞 공백 포함, 문맥 안)와 단어 빈도."""
    base = {name: t.count(CONTEXT) for name, t in toks.items()}
    out = []
    for shape in SHAPES:
        for f in shape_forms(shape):
            zipf = max(zipf_frequency(f, lang) for lang in WORD_LANGS)
            if zipf >= 3.0:
                continue
            cost = {name: t.count(f"{CONTEXT} {f}") - base[name] for name, t in toks.items()}
            out.append({"form": f, "zipf": zipf, "cost": cost, "mean": statistics.mean(cost.values())})
    out.sort(key=lambda r: (r["mean"], max(r["cost"].values()), r["zipf"], len(r["form"]), r["form"]))
    return out


def parse_gloss(text: str) -> list[str]:
    """뜻풀이 문자열 → 표지 목록. 따옴표 안 공백이 있는 원문(RAW/STR)은 한 덩어리로 묶는다."""
    text = text.replace("|", " ")
    items = re.findall(r'(?:RAW|STR):"[^"]*"|\S+', text)
    return items


def realize(items: list[str], k: int, scenario: str) -> list[tuple[str, str]]:
    """시나리오를 적용해 (종류, 값) 목록을 만든다. 종류: lex(형태소), raw(원문), digits(아라비아 숫자)."""
    level = SCENARIOS.index(scenario)
    prag = PRAG[k]
    out: list[tuple[str, str]] = []
    i = 0
    while i < len(items):
        tok = items[i]
        kind, _, val = tok.partition(":")
        if kind == "ZERO":
            i += 1
            continue
        if kind in ("RAW", "STR"):
            out.append(("raw", val.strip('"')))
            i += 1
            continue
        if kind == "AFF" and prag["member"](val):
            # 한 절의 화행·확신도·증거성 묶음을 모은다
            group = [val]
            j = i + 1
            while j < len(items) and items[j].startswith("AFF:") and prag["member"](items[j][4:]) \
                    and not prag["act"](items[j][4:]):
                group.append(items[j][4:])
                j += 1
            if level == 0:
                out += [("lex", f"AFF:{g}") for g in group]
            elif level == 1:
                out += [("lex", f"AFF:{g}") for g in group if g not in prag["default"]]
            else:
                non_default = sorted(g for g in group if g not in prag["default"])
                if non_default:
                    out.append(("lex", "AFF:PRAG[" + "+".join(non_default) + "]"))
            i = j
            continue
        if kind == "AFF" and level >= 3 and val in CORE_ROLES:
            i += 1
            continue
        if kind == "AFF" and level >= 4 and val in LINKERS:
            i += 1
            continue
        is_marker = kind == "NUM" and val in ("", "#")
        is_digit = kind in ("DIG", "NUM") and val.isdigit()
        is_point = (kind == "DIG" and val == "point") or (kind == "NUM" and val == "pt")
        if level >= 5 and (is_marker or is_digit or is_point):
            # 숫자 표지는 버리고 자릿수를 아라비아 숫자 문자열로 모은다
            if is_marker or not out or out[-1][0] != "digits":
                out.append(("digits", ""))
            if not is_marker:
                out[-1] = ("digits", out[-1][1] + (val if is_digit else "."))
            i += 1
            continue
        out.append(("lex", tok))
        i += 1
    return out


def build_lexicon(seqs: list[list[tuple[str, str]]], forms: list[dict]) -> dict[str, str]:
    """자주 쓰는 형태소에 싼 형태를 준다. 닫힌 부류가 먼저, 어근은 1,000개 어휘 안에 고르게 흩어진다고 가정."""
    freq: dict[str, int] = {}
    for seq in seqs:
        for kind, val in seq:
            if kind == "lex":
                freq[val] = freq.get(val, 0) + 1
    closed = sorted((v for v in freq if not v.startswith("ROOT:")), key=lambda v: (-freq[v], v))
    roots = sorted((v for v in freq if v.startswith("ROOT:")), key=lambda v: (-freq[v], v))
    if len(closed) > N_CLOSED:
        raise ValueError(f"closed-class labels {len(closed)} > {N_CLOSED}")
    lex = {v: forms[i]["form"] for i, v in enumerate(closed)}
    step = ROOT_LEXICON / max(len(roots), 1)
    for i, v in enumerate(roots):
        lex[v] = forms[N_CLOSED + int(i * step)]["form"]
    return lex


def render(seq: list[tuple[str, str]], lex: dict[str, str]) -> str:
    parts = []
    for kind, val in seq:
        if val:
            parts.append(lex[val] if kind == "lex" else val)
    return " ".join(parts)


def main() -> None:
    t0 = time.time()
    toks = load_all()
    corpus = {m["id"]: m for m in json.loads((HERE / "corpus" / "ai_messages.json").read_text())}
    glosses = {k: json.loads((HERE / "corpus" / f"gloss_{k}.json").read_text()) for k in (1, 2)}
    baseline = json.loads((HERE / "results" / "baseline.json").read_text())["per_message"]

    forms = form_costs(toks)

    def total(variant: str, name: str) -> int:
        return sum(baseline[mid][name][variant] for mid in corpus)

    report = {"meta": {"scenarios": SCENARIOS, "n_messages": len(corpus), "n_candidate_forms": len(forms),
                       "n_closed_slots": N_CLOSED, "root_lexicon": ROOT_LEXICON,
                       "form_cost_top": {"closed_per_tokenizer": {n: statistics.mean(f["cost"][n] for f in forms[:N_CLOSED]) for n in toks},
                                         "roots_per_tokenizer": {n: statistics.mean(f["cost"][n] for f in forms[N_CLOSED:N_CLOSED + ROOT_LEXICON]) for n in toks}}},
              "baseline": {n: {"en": total("en", n), "en_terse": total("en_terse", n)} for n in toks},
              "glosses": {}}
    examples = {}
    for k, g in glosses.items():
        per = {}
        for scen in SCENARIOS:
            seqs = [realize(parse_gloss(m["gloss_strict"]), k, scen) for m in g["messages"]]
            lex = build_lexicon(seqs, forms)  # 시나리오마다 그 문법에 맞춘 어휘를 따로 배정한다
            morphemes, tokens = 0, {n: 0 for n in toks}
            for m, seq in zip(g["messages"], seqs):
                morphemes += sum(1 for kind, _ in seq if kind == "lex")
                text = render(seq, lex)
                for n, t in toks.items():
                    tokens[n] += t.count(text)
                if m["id"] == "m01":
                    examples.setdefault(k, {})[scen] = text
            per[scen] = {"morphemes": morphemes, "morphemes_per_msg": morphemes / len(g["messages"]),
                         "tokens": tokens,
                         "ratio_vs_en": {n: tokens[n] / report["baseline"][n]["en"] for n in toks},
                         "ratio_vs_en_terse": {n: tokens[n] / report["baseline"][n]["en_terse"] for n in toks}}
        report["glosses"][k] = per
    report["examples_m01"] = {"en": corpus["m01"]["en"], "en_terse": corpus["m01"]["en_terse"], **{f"gloss_{k}": v for k, v in examples.items()}}
    report["meta"]["runtime_sec"] = round(time.time() - t0, 1)
    (HERE / "results" / "projection.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    (HERE / "results" / "projection.md").write_text(to_markdown(report, list(toks)))
    print((HERE / "results" / "projection.md").read_text())


def to_markdown(r: dict, names: list[str]) -> str:
    focus = ["o200k", "claude_legacy", "llama3", "mistral_tekken"]
    lines = ["# 투영: 초안 문법의 실제 토큰 비용", "",
             "`projection.py`가 만든다. 두 추정자의 형태소 분석(corpus/gloss_1.json, gloss_2.json)을 W2 표기(형태소마다 띄어쓰기)의 실제 문자열로 바꿔 잰 값이다.", "",
             f"- 후보 형태: {r['meta']['n_candidate_forms']:,}개 ({', '.join(SHAPES)}, 11개 언어 max zipf < 3.0)",
             f"- 닫힌 부류(접사·표지·숫자·변수)에 가장 싼 형태 {r['meta']['n_closed_slots']}개, 어근은 그다음 {r['meta']['root_lexicon']:,}개 안에 고르게 배정",
             "- 형태당 평균 토큰 (앞 공백 포함, 닫힌 부류 / 어근): " + ", ".join(
                 f"{n} {r['meta']['form_cost_top']['closed_per_tokenizer'][n]:.2f} / {r['meta']['form_cost_top']['roots_per_tokenizer'][n]:.2f}" for n in names), "",
             "## 메시지 40개 합계 토큰과 영어 대비 비율", ""]
    lines.append("| 추정자 | 시나리오 | 형태소/메시지 | " + " | ".join(f"{n} (en·terse 대비)" for n in focus) + " |")
    lines.append("|---|---|---|" + "---|" * len(focus))
    for k, per in r["glosses"].items():
        for scen, v in per.items():
            cells = [f"{v['tokens'][n]:,} ({v['ratio_vs_en'][n]:.2f}·{v['ratio_vs_en_terse'][n]:.2f})" for n in focus]
            lines.append(f"| {k} | {scen} | {v['morphemes_per_msg']:.1f} | " + " | ".join(cells) + " |")
    lines += ["", "기준선 합계: " + ", ".join(f"{n} en {r['baseline'][n]['en']:,} / terse {r['baseline'][n]['en_terse']:,}" for n in focus), "",
              "## 예시 (m01)", "", f"- en: {r['examples_m01']['en']}", f"- en_terse: {r['examples_m01']['en_terse']}"]
    for key in ("gloss_1", "gloss_2"):
        for scen in ("S0_strict", "S5_raw_digits"):
            lines.append(f"- {key} {scen}: `{r['examples_m01'][key][scen]}`")
    lines += ["", "## 한계", "",
              "- 형태소 수는 두 추정자가 손으로 단 분석에 기댄다. 실제 문법이 정해지면 달라진다.",
              "- S3(어순으로 역할 표시)은 생략된 논항과 겹칠 때의 모호성을 따지지 않은 낙관적 추정이다.",
              "- 어근 배정은 '말뭉치에 나온 어근이 1,000개 어휘 안에 고르게 흩어져 있다'는 가정이다.",
              "- 현행 Claude 토크나이저는 공개되지 않았다. claude_legacy는 대용 지표다.",
              "- LLM이 이 문자열을 실제로 정확히 읽고 쓰는지는 재지 않았다."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
