"""E3 기준선: AI끼리 주고받는 메시지를 기존 표기로 적으면 토큰이 몇 개인가.

`corpus/ai_messages.json` 의 메시지 40개를 네 가지 표기로 적은 것을 7개 토크나이저로 센다.
이 언어가 이겨야 할 상대(기준선)의 토큰 비용을 정하는 실험이다.

표기 (같은 정보를 담는다)
- en       : 유능한 에이전트가 쓸 법한 간결한 영어. 비율의 기준(분모)이다.
- en_terse : 사양 없이도 다른 LLM이 알아듣는 전보체 영어 (관사·계사 생략, 약어, 기호).
             사양이 필요 없는 가장 강한 경쟁자다. 약어는 토큰을 실제로 줄일 때만 썼다.
- ko       : 자연스러운 한국어
- json     : 개발자가 에이전트 사이에 넘길 법한 압축 JSON (짧은 키, 공백 없음)
- oracle_min (파생) : 메시지마다 en, en_terse, json 가운데 가장 적은 토큰 수. 사양 없는 표기의 사후 최선값이다.

메시지는 따로따로 보낸다고 보고 메시지마다 세어 더한다. 채팅 템플릿이나 메시지 머리말 같은 부가 토큰은 세지 않는다.

탈출 대상 판정 (en 기준 휴리스틱, 이 언어가 원문 철자 그대로 인용해야 할 것)
- url        : http(s):// 로 시작하는 문자열
- number     : 숫자가 있는 단어
- identifier : 글자가 섞인 단어 안에 / _ . 가 있거나, 괄호 () 로 끝나거나, camelCase 인 것 (파일명, 경로, 코드 식별자).
               숫자뿐인 버전(3.11)은 number 로만 센다.
- proper     : 문장 첫머리가 아닌 곳의 대문자 시작 단어 (I 제외). 전부 대문자인 약어(SQL, API, HTTP, GPU, ID)는
               이 언어의 일반 어휘로 보고 세지 않는다.

통계
- median, p90 : 메시지 40개의 분포. p90 은 statistics.quantiles(n=10, method="inclusive") 의 9번째 값이다.
- ratio_total : 표기 합계 / en 합계
- ratio_msg   : 메시지마다 (표기 / en) 을 구한 뒤의 분포 (median, p90)

무작위 요소가 없으므로 결과는 항상 같다.

사용법
    python3 baseline.py      # results/baseline.json, results/baseline.md 생성
"""

from __future__ import annotations

import json
import re
import statistics
import time
from pathlib import Path

from toklib import load_all

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus" / "ai_messages.json"
OUT_JSON = HERE / "results" / "baseline.json"
OUT_MD = HERE / "results" / "baseline.md"
ALIGNMENT_JSON = HERE / "results" / "alignment.json"  # E2 결과 (있으면 형태소 예산 계산에 쓴다)

VARIANTS = ["en", "en_terse", "ko", "json"]
DERIVED = ["oracle_min"]
ALL_VARIANTS = VARIANTS + DERIVED
REF = "en"
ORACLE_FROM = ["en", "en_terse", "json"]
CATEGORIES = ["delegation", "status", "tool_result", "clarification", "error",
              "plan", "review", "negotiation", "final_answer", "handoff"]
FIELDS = ["id", "category", "en", "en_terse", "ko", "json"]
N_EXPECTED = 40

_URL = re.compile(r"https?://\S+")
_WORD = re.compile(r"\S+")
_SENT_END = re.compile(r"[.?!](?=\s|$)")


# ---------------------------------------------------------------- 코퍼스

def load_corpus() -> list[dict]:
    """코퍼스를 읽고 형식을 검사한다."""
    msgs = json.loads(CORPUS.read_text(encoding="utf-8"))
    assert isinstance(msgs, list) and len(msgs) == N_EXPECTED, f"메시지 {N_EXPECTED}개가 필요하다: {len(msgs)}"
    ids = set()
    for m in msgs:
        assert list(m.keys()) == FIELDS, f"{m.get('id')}: 필드가 {FIELDS} 가 아니다"
        assert m["id"] not in ids, f"id 중복: {m['id']}"
        ids.add(m["id"])
        assert m["category"] in CATEGORIES, f"{m['id']}: 모르는 범주 {m['category']}"
        compact = json.dumps(json.loads(m["json"]), separators=(",", ":"), ensure_ascii=False)
        assert compact == m["json"], f"{m['id']}: json 필드가 압축 JSON 이 아니다"
    return msgs


def escape_kinds(text: str) -> list[str]:
    """en 문장에서 탈출(원문 인용)이 필요한 요소의 종류를 찾는다. 모듈 설명의 휴리스틱."""
    kinds = set()
    if _URL.search(text):
        kinds.add("url")
    rest = _URL.sub(" ", text)
    sentence_start = True
    for mt in _WORD.finditer(rest):
        raw = mt.group()
        word = raw.strip("\"'(),;:.?!")
        if any(ch.isdigit() for ch in word):
            kinds.add("number")
        if (re.search(r"[A-Za-z0-9][/_.][A-Za-z0-9]", word) and re.search(r"[A-Za-z]", word)) \
                or raw.rstrip(",;:.?!").endswith("()") or re.fullmatch(r"[a-z]+[A-Z]\w*", word):
            kinds.add("identifier")
        if (not sentence_start and word and word[0].isupper() and word != "I"
                and not word.isupper() and "_" not in word):
            kinds.add("proper")
        sentence_start = raw.endswith((".", "?", "!", ":"))
    return sorted(kinds)


def n_sentences(text: str) -> int:
    return max(1, len(_SENT_END.findall(text)))


# ---------------------------------------------------------------- 통계

def p90(xs: list[float]) -> float:
    return statistics.quantiles(xs, n=10, method="inclusive")[-1]


def dist(xs: list[float]) -> dict:
    return {"mean": statistics.mean(xs), "median": statistics.median(xs), "p90": p90(xs),
            "min": min(xs), "max": max(xs)}


def summarize(counts: dict[str, dict[str, int]], ids: list[str], chars: dict[str, dict[str, int]]) -> dict:
    """한 토크나이저의 표기별 요약. counts[variant][id] = 토큰 수."""
    out = {}
    ref_total = sum(counts[REF][i] for i in ids)
    for v in ALL_VARIANTS:
        xs = [counts[v][i] for i in ids]
        total = sum(xs)
        ratios = [counts[v][i] / counts[REF][i] for i in ids]
        row = {"total": total, **dist(xs),
               "ratio_total": total / ref_total,
               "ratio_msg_median": statistics.median(ratios), "ratio_msg_p90": p90(ratios),
               "share_below_en": sum(counts[v][i] < counts[REF][i] for i in ids) / len(ids),
               "share_above_en": sum(counts[v][i] > counts[REF][i] for i in ids) / len(ids)}
        if v in chars:
            row["chars_per_token"] = sum(chars[v][i] for i in ids) / total
        out[v] = row
    return out


def subset_totals(counts: dict[str, dict[str, int]], ids: list[str]) -> dict:
    tot = {v: sum(counts[v][i] for i in ids) for v in ALL_VARIANTS}
    return {"n": len(ids), "total": tot,
            "mean": {v: tot[v] / len(ids) for v in ALL_VARIANTS},
            "ratio_total": {v: tot[v] / tot[REF] for v in ALL_VARIANTS}}


def alignment_tpm() -> dict[str, float] | None:
    """E2 의 W2_spaced + token_picked 토큰/형태소 값을 읽는다. 없으면 None."""
    if not ALIGNMENT_JSON.exists():
        return None
    try:
        data = json.loads(ALIGNMENT_JSON.read_text(encoding="utf-8"))
        return {r["tokenizer"]: r["tokens_per_morpheme"] for r in data["results"]
                if r.get("design") == "W2_spaced" and r.get("inventory") == "token_picked"} or None
    except (KeyError, TypeError, ValueError):
        return None


# ---------------------------------------------------------------- 측정

def measure() -> dict:
    t0 = time.time()
    msgs = load_corpus()
    toks = load_all()
    ids = [m["id"] for m in msgs]
    by_id = {m["id"]: m for m in msgs}

    chars = {v: {m["id"]: len(m[v]) for m in msgs} for v in VARIANTS}
    esc = {m["id"]: escape_kinds(m["en"]) for m in msgs}
    esc_ids = [i for i in ids if esc[i]]
    plain_ids = [i for i in ids if not esc[i]]

    per_message: dict[str, dict[str, dict[str, int]]] = {i: {} for i in ids}
    per_tok, by_cat, by_esc = {}, {}, {}
    for name, tok in toks.items():
        counts = {v: {m["id"]: tok.count(m[v]) for m in msgs} for v in VARIANTS}
        counts["oracle_min"] = {i: min(counts[v][i] for v in ORACLE_FROM) for i in ids}
        for i in ids:
            per_message[i][name] = {v: counts[v][i] for v in ALL_VARIANTS}
        per_tok[name] = summarize(counts, ids, chars)
        by_cat[name] = {c: subset_totals(counts, [i for i in ids if by_id[i]["category"] == c]) for c in CATEGORIES}
        by_esc[name] = {"with_escape": subset_totals(counts, esc_ids), "without_escape": subset_totals(counts, plain_ids)}

    names = list(toks)
    cross = {}
    for v in ALL_VARIANTS:
        rs = [per_tok[n][v]["ratio_total"] for n in names]
        cross[v] = {"ratio_total_mean": statistics.mean(rs), "ratio_total_min": min(rs), "ratio_total_max": max(rs),
                    "argmin": names[rs.index(min(rs))], "argmax": names[rs.index(max(rs))]}
    oracle_pick = {v: sum(per_message[i][n]["oracle_min"] == per_message[i][n][v] for i in ids for n in names)
                   for v in ORACLE_FROM}

    sents = [n_sentences(by_id[i]["en"]) for i in ids]
    tpm = alignment_tpm()
    budget = None
    if tpm:
        budget = {n: {"tokens_per_morpheme_w2_token_picked": tpm[n],
                      "morphemes_per_msg_to_match_en": per_tok[n]["en"]["mean"] / tpm[n],
                      "morphemes_per_msg_to_match_en_terse": per_tok[n]["en_terse"]["mean"] / tpm[n]}
                  for n in names if n in tpm}

    return {
        "meta": {
            "experiment": "E3 baseline",
            "corpus": str(CORPUS.relative_to(HERE)),
            "n_messages": len(msgs),
            "variants": VARIANTS, "derived": {"oracle_min": f"min({', '.join(ORACLE_FROM)}) per message"},
            "reference": REF,
            "p90_method": "statistics.quantiles(n=10, method='inclusive')[-1]",
            "counting": "message by message, no chat template or wrapper tokens",
            "tokenizers": {n: t.description for n, t in toks.items()},
            "runtime_sec": round(time.time() - t0, 1),
        },
        "corpus_stats": {
            "categories": {c: sum(by_id[i]["category"] == c for i in ids) for c in CATEGORIES},
            "sentences_en": {"histogram": {str(k): sents.count(k) for k in sorted(set(sents))},
                             "median": statistics.median(sents), "mean": statistics.mean(sents)},
            "chars": {v: {"total": sum(chars[v].values()), **dist(list(chars[v].values()))} for v in VARIANTS},
            "escape_ids": esc_ids,
            "escape_kinds": {i: esc[i] for i in esc_ids},
            "escape_kind_counts": {k: sum(k in esc[i] for i in ids) for k in ["url", "number", "identifier", "proper"]},
        },
        "per_tokenizer": per_tok,
        "cross_tokenizer": cross,
        "oracle_pick_counts": oracle_pick,
        "by_category": by_cat,
        "by_escape": by_esc,
        "morpheme_budget": budget,
        "per_message": per_message,
    }


# ---------------------------------------------------------------- 보고서

def _f(x: float, d: int = 2) -> str:
    return f"{x:.{d}f}"


def _pct(x: float) -> str:
    return f"{x * 100:+.0f}%"


def write_md(res: dict, msgs: list[dict]) -> str:
    names = list(res["per_tokenizer"])
    pt, cs, cross = res["per_tokenizer"], res["corpus_stats"], res["cross_tokenizer"]
    L: list[str] = []
    w = L.append

    w("# E3 기준선: AI 메시지 코퍼스의 토큰 비용")
    w("")
    w("`baseline.py` 가 만든 요약이다. 숫자는 모두 이 스크립트로 잰 값이며, 원자료는 `baseline.json` 에 있다. "
      f"코퍼스는 `{res['meta']['corpus']}` (메시지 {res['meta']['n_messages']}개)다.")
    w("")

    # 0. 요약
    w("## 0. 요약")
    w("")
    items: list[str] = []
    en_tot = {n: pt[n]["en"]["total"] for n in names}
    lo_n, hi_n = min(en_tot, key=en_tot.get), max(en_tot, key=en_tot.get)
    items.append(f"**en 기준선**: 메시지 40개 합계 {en_tot[lo_n]} ({lo_n}) ~ {en_tot[hi_n]} ({hi_n}) 토큰, "
                 f"o200k 기준 메시지당 평균 {_f(pt['o200k']['en']['mean'], 1)}, median {_f(pt['o200k']['en']['median'], 1)}, "
                 f"p90 {_f(pt['o200k']['en']['p90'], 1)} 토큰.")
    for v, label in [("en_terse", "en_terse (전보체, 사양 없는 최강 경쟁자)"), ("ko", "ko (한국어)"), ("json", "json (압축 JSON)")]:
        c = cross[v]
        items.append(f"**{label}**: en 대비 합계 비율 {_f(c['ratio_total_min'])} ({c['argmin']}) ~ {_f(c['ratio_total_max'])} "
                     f"({c['argmax']}), 7개 평균 {_f(c['ratio_total_mean'])}. o200k {_f(pt['o200k'][v]['ratio_total'])}, "
                     f"claude_legacy {_f(pt['claude_legacy'][v]['ratio_total'])}. "
                     f"en 보다 적은 메시지 비율 (o200k) {pt['o200k'][v]['share_below_en'] * 100:.0f}%.")
    c = cross["oracle_min"]
    items.append(f"**oracle_min** (메시지마다 en / en_terse / json 중 최소): en 대비 {_f(c['ratio_total_min'])} ~ "
                 f"{_f(c['ratio_total_max'])}, 평균 {_f(c['ratio_total_mean'])}. "
                 "최소값을 낸 표기 횟수 (메시지 × 토크나이저 280칸, 동률은 모두 셈): "
                 + ", ".join(f"{v} {k}" for v, k in res["oracle_pick_counts"].items()) + ".")
    e_with = statistics.mean(res["by_escape"][n]["with_escape"]["ratio_total"]["en_terse"] for n in names)
    e_wo = statistics.mean(res["by_escape"][n]["without_escape"]["ratio_total"]["en_terse"] for n in names)
    j_with = statistics.mean(res["by_escape"][n]["with_escape"]["ratio_total"]["json"] for n in names)
    j_wo = statistics.mean(res["by_escape"][n]["without_escape"]["ratio_total"]["json"] for n in names)
    n_esc = len(cs["escape_ids"])
    items.append(f"**탈출 대상(숫자, 경로, 식별자, URL, 고유명사)이 있는 메시지 {n_esc}개 vs 없는 메시지 {40 - n_esc}개** "
                 f"(7개 평균 en 대비 비율): en_terse {_f(e_with)} vs {_f(e_wo)}, json {_f(j_with)} vs {_f(j_wo)}. "
                 f"o200k 메시지당 평균 en 토큰 {_f(res['by_escape']['o200k']['with_escape']['mean']['en'], 1)} vs "
                 f"{_f(res['by_escape']['o200k']['without_escape']['mean']['en'], 1)}.")
    goal = (f"**이 언어의 목표선**: 사양 없이 읽히는 en_terse 를 이기려면 메시지당 평균 토큰이 "
            f"o200k {_f(pt['o200k']['en_terse']['mean'], 1)}, claude_legacy {_f(pt['claude_legacy']['en_terse']['mean'], 1)} "
            f"보다 적어야 한다 (en 은 {_f(pt['o200k']['en']['mean'], 1)} / {_f(pt['claude_legacy']['en']['mean'], 1)}).")
    budget = res["morpheme_budget"]
    if budget and "o200k" in budget and "claude_legacy" in budget:
        goal += (f" E2 의 W2_spaced + token_picked 토큰/형태소로 환산하면 메시지당 형태소 "
                 f"o200k {_f(budget['o200k']['morphemes_per_msg_to_match_en_terse'], 1)}개, "
                 f"claude_legacy {_f(budget['claude_legacy']['morphemes_per_msg_to_match_en_terse'], 1)}개 미만이다 (7절).")
    goal += " 사양(수천 토큰)을 컨텍스트에 넣는 비용은 이 비교에 들어 있지 않다."
    items.append(goal)
    for k, it in enumerate(items, 1):
        w(f"{k}. {it}")
    w("")

    # 1. 코퍼스
    w("## 1. 코퍼스")
    w("")
    w("범주별 메시지 수: " + ", ".join(f"{c} {k}" for c, k in cs["categories"].items()) + ".")
    w("")
    hist = cs["sentences_en"]["histogram"]
    w("en 문장 수 분포: " + ", ".join(f"{k}문장 {v}개" for k, v in hist.items())
      + f" (median {_f(cs['sentences_en']['median'], 1)}, 평균 {_f(cs['sentences_en']['mean'], 2)}). "
      "문장은 공백이나 끝 앞의 . ? ! 로 센다.")
    w("")
    w("| 표기 | 글자 합계 | 메시지당 median | p90 | 최소 | 최대 |")
    w("|---|---:|---:|---:|---:|---:|")
    for v in VARIANTS:
        d = cs["chars"][v]
        w(f"| {v} | {d['total']} | {_f(d['median'], 1)} | {_f(d['p90'], 1)} | {d['min']} | {d['max']} |")
    w("")
    w("작성 방침")
    w("")
    w("- 네 표기는 같은 정보를 담는다. 작은 수는 en 에서 낱말(five)로, en_terse 와 json 에서는 숫자로 적었다.")
    w("- en_terse 는 관사·계사를 빼고 `->`, `=`, `+`, `~`, `;` 같은 기호를 쓴다. 약어는 토크나이저로 재 보고 토큰을 늘리지 않을 때만 남겼다 "
      "(예: `w/`, `Ctx`, `2nd`, `O(n^2)` 는 `with`, `Context`, `second`, `quadratic` 보다 토큰이 많아 쓰지 않았다).")
    w("- json 은 짧은 키, 공백 없는 직렬화(`separators=(',', ':')`), 값은 대부분 snake_case 다. 고유명사와 URL 은 원문 그대로 둔다.")
    w("- ko 는 자연스러운 한국어다. 외국 인명·지명은 한글로 옮겼고, 경로·식별자·URL 은 원문 그대로 둔다.")
    w("- 실존 서비스 URL 은 Python 문서 하나뿐이고, 나머지 이름(인물, 저장소 example-org/tilemap)은 가상이다.")
    w("")
    w(f"탈출 대상이 있는 메시지 ({n_esc}/40, en 기준 휴리스틱, 종류별 메시지 수: "
      + ", ".join(f"{k} {v}" for k, v in cs["escape_kind_counts"].items()) + ")")
    w("")
    w("| id | 범주 | 종류 |")
    w("|---|---|---|")
    cat_of = {m["id"]: m["category"] for m in msgs}
    for i, k in cs["escape_kinds"].items():
        w(f"| {i} | {cat_of[i]} | {', '.join(k)} |")
    w("")

    # 2. 합계와 비율
    w("## 2. 토크나이저별 합계와 en 대비 비율")
    w("")
    w("셀 = 메시지 40개 토큰 합계 (en 합계 대비 비율). chars/token 은 en 기준이다.")
    w("")
    w("| 토크나이저 | en | en_terse | ko | json | oracle_min | en chars/token |")
    w("|---|---:|---:|---:|---:|---:|---:|")
    for n in names:
        cells = [str(pt[n]["en"]["total"])] + [f"{pt[n][v]['total']} ({_f(pt[n][v]['ratio_total'])})" for v in ALL_VARIANTS[1:]]
        w(f"| {n} | " + " | ".join(cells) + f" | {_f(pt[n]['en']['chars_per_token'])} |")
    w("| **7개 평균 비율** | 1.00 | " + " | ".join(_f(cross[v]["ratio_total_mean"]) for v in ALL_VARIANTS[1:]) + " | |")
    w("")

    # 3. 메시지당 분포
    w("## 3. 메시지당 토큰 수 분포")
    w("")
    w("셀 = median / p90 (메시지 40개).")
    w("")
    w("| 토크나이저 | " + " | ".join(ALL_VARIANTS) + " |")
    w("|---|" + "---:|" * len(ALL_VARIANTS))
    for n in names:
        w(f"| {n} | " + " | ".join(f"{_f(pt[n][v]['median'], 1)} / {_f(pt[n][v]['p90'], 1)}" for v in ALL_VARIANTS) + " |")
    w("")

    # 4. 메시지별 비율 분포
    w("## 4. 메시지별 en 대비 비율의 분포")
    w("")
    w("셀 = 메시지마다 구한 (표기 / en) 의 median / p90, 괄호는 en 보다 토큰이 적은 메시지 비율.")
    w("")
    w("| 토크나이저 | en_terse | ko | json | oracle_min |")
    w("|---|---:|---:|---:|---:|")
    for n in names:
        w(f"| {n} | " + " | ".join(
            f"{_f(pt[n][v]['ratio_msg_median'])} / {_f(pt[n][v]['ratio_msg_p90'])} ({pt[n][v]['share_below_en'] * 100:.0f}%)"
            for v in ALL_VARIANTS[1:]) + " |")
    w("")

    # 5. 범주별
    w("## 5. 범주별")
    w("")
    w("en 은 o200k 메시지당 평균 토큰, 나머지는 범주 안 합계 비율(표기 / en)의 7개 토크나이저 평균이다.")
    w("")
    w("| 범주 | n | en (o200k 평균) | en_terse | ko | json | oracle_min |")
    w("|---|---:|---:|---:|---:|---:|---:|")
    for c in CATEGORIES:
        bc = {n: res["by_category"][n][c] for n in names}
        w(f"| {c} | {bc['o200k']['n']} | {_f(bc['o200k']['mean']['en'], 1)} | "
          + " | ".join(_f(statistics.mean(bc[n]["ratio_total"][v] for n in names)) for v in ALL_VARIANTS[1:]) + " |")
    w("")

    # 6. 탈출 대상
    w("## 6. 탈출 대상 포함 여부별")
    w("")
    w("셀 = 메시지당 평균 토큰 (en 대비 합계 비율).")
    w("")
    w("| 토크나이저 | 부분집합 | n | en | en_terse | ko | json |")
    w("|---|---|---:|---:|---:|---:|---:|")
    for n in names:
        for key, label in [("with_escape", "탈출 있음"), ("without_escape", "탈출 없음")]:
            b = res["by_escape"][n][key]
            w(f"| {n} | {label} | {b['n']} | {_f(b['mean']['en'], 1)} | "
              + " | ".join(f"{_f(b['mean'][v], 1)} ({_f(b['ratio_total'][v])})" for v in ["en_terse", "ko", "json"]) + " |")
    w("")

    # 7. 목표선
    w("## 7. 이 언어의 목표선")
    w("")
    w("이 언어가 같은 메시지를 아래 토큰 수보다 적게 써야 각 기준선을 이긴다 (메시지당 평균).")
    w("")
    budget = res["morpheme_budget"]
    if budget:
        w("E2(`alignment.json`)의 W2_spaced + token_picked 토큰/형태소 값으로 나누면 메시지당 쓸 수 있는 형태소 수가 된다. "
          "E2 값은 이 스크립트를 실행한 시점의 `alignment.json` 에서 읽었다.")
        w("")
        w("| 토크나이저 | en | en_terse | oracle_min | E2 토큰/형태소 | 형태소 예산 (= en) | 형태소 예산 (= en_terse) |")
        w("|---|---:|---:|---:|---:|---:|---:|")
        for n in names:
            b = budget.get(n)
            tail = (f"{_f(b['tokens_per_morpheme_w2_token_picked'])} | {_f(b['morphemes_per_msg_to_match_en'], 1)} | "
                    f"{_f(b['morphemes_per_msg_to_match_en_terse'], 1)}") if b else "- | - | -"
            w(f"| {n} | {_f(pt[n]['en']['mean'], 1)} | {_f(pt[n]['en_terse']['mean'], 1)} | "
              f"{_f(pt[n]['oracle_min']['mean'], 1)} | {tail} |")
    else:
        w("(`alignment.json` 이 없어 형태소 예산은 계산하지 않았다.)")
        w("")
        w("| 토크나이저 | en | en_terse | oracle_min |")
        w("|---|---:|---:|---:|")
        for n in names:
            w(f"| {n} | {_f(pt[n]['en']['mean'], 1)} | {_f(pt[n]['en_terse']['mean'], 1)} | {_f(pt[n]['oracle_min']['mean'], 1)} |")
    w("")

    # 8. 한계
    w("## 8. 한계")
    w("")
    w("- 코퍼스는 한 모델이 한 번에 쓴 40개 메시지다. 문체가 한쪽으로 치우쳤을 수 있고, 표본이 작아 비율의 소수 둘째 자리는 믿기 어렵다.")
    w("- 네 표기가 정말 같은 정보를 담는지는 작성자가 맞췄을 뿐 사람이나 다른 모델이 검증하지 않았다. "
      "en_terse 가 사양 없이 정확히 이해되는지도 모델 API 없이 확인할 수 없어 재지 않았다.")
    w("- 현행 Claude 토크나이저는 공개되지 않았다. claude_legacy 는 대용 지표다.")
    w("- en_terse 의 약어 선택은 이 토크나이저들로 재 보며 골랐으므로 경쟁자에게 유리한 쪽으로 치우쳐 있다 (의도한 것이다).")
    w("- json 은 짧은 키와 snake_case 값을 쓴 비교적 압축된 형태다. 실제 에이전트 사이 JSON 은 키가 더 길거나 공백이 들어가 더 비쌀 수 있다.")
    w("- 탈출 대상 판정은 휴리스틱이다. 전부 대문자인 약어는 세지 않는다.")
    w("- 채팅 템플릿, 역할 표지 같은 메시지 부가 토큰과 사양(컨텍스트) 비용은 세지 않았다.")
    w("")

    # 부록
    w("## 부록: 메시지별 토큰 수")
    w("")
    w("셀 = o200k / claude_legacy.")
    w("")
    w("| id | 범주 | en | en_terse | ko | json |")
    w("|---|---|---:|---:|---:|---:|")
    pm = res["per_message"]
    for m in msgs:
        i = m["id"]
        w(f"| {i} | {m['category']} | " + " | ".join(
            f"{pm[i]['o200k'][v]} / {pm[i]['claude_legacy'][v]}" for v in VARIANTS) + " |")
    w("")
    return "\n".join(L)


def main() -> None:
    res = measure()
    msgs = load_corpus()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    OUT_MD.write_text(write_md(res, msgs), encoding="utf-8")
    pt = res["per_tokenizer"]
    print(f"{'tokenizer':15} " + " ".join(f"{v:>16}" for v in ALL_VARIANTS))
    for n, row in pt.items():
        print(f"{n:15} " + " ".join(f"{row[v]['total']:>8} ({row[v]['ratio_total']:.2f})" for v in ALL_VARIANTS))
    print(f"escape ids ({len(res['corpus_stats']['escape_ids'])}):", res["corpus_stats"]["escape_kinds"])
    print(f"wrote {OUT_JSON.relative_to(HERE)}, {OUT_MD.relative_to(HERE)} in {res['meta']['runtime_sec']}s")


if __name__ == "__main__":
    main()
