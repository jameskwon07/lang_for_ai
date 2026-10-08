"""실험 E1: 형태소 후보 목록(inventory) 조사.

글자 배열 모양(CVC, VC …)과 표기(소문자, 앞 공백, 첫 글자 대문자)마다
후보 형태 가운데 몇 개가 토크나이저 7종에서 토큰 하나로 끝나는지 센다.
여러 언어의 실제 단어와 겹치는 형태는 LLM에게 원래 뜻을 끌고 오므로(의미 간섭) 단어 빈도로 거른다.

사용법 (이 디렉터리에서)
    python3 inventory.py      # results/inventory.json, results/inventory.md 생성 (4 프로세스로 약 1분)

측정 방법
- 형태 하나를 문맥 뒤에 붙여 토큰화하고, 문맥이 끝나는 위치 뒤의 토큰만 센다.
  문맥 토큰과 형태가 한 토큰으로 합쳐지면(경계가 없으면) 단일 토큰이 아닌 것으로 친다.
    앞 공백 표기 (" kat", " Kat") : 문맥 "the"  → "the kat"   문장 중간에서 공백 뒤에 오는 형태
    붙임 표기   ("kat", "Kat")   : 문맥 "1"    → "1kat"      공백 없이 시작하는 형태 (붙여 쓰기용)
- 문맥이 필요한 까닭: SentencePiece(mistral_sp)는 입력 맨 앞에 가짜 공백(▁)을 붙이므로
  "kat"을 홀로 토큰화하면 사실은 "▁kat"(= 앞 공백 표기)을 재고, " kat"을 홀로 토큰화하면 "▁▁kat"을 잰다.
  다른 토크나이저는 사전 분할(pre-tokenization) 정규식이 숫자와 글자, 단어와 공백을 이미 나누므로
  문맥이 있어도 결과가 같다. 이를 sanity 항목에서 실제로 확인한다.
- 붙임 표기의 단일 토큰 여부는 "형태가 글자 덩어리의 맨 앞에 올 때"의 값이다.
  글자가 계속 이어지는 문자열(katenmirob) 안에서 이웃 글자와 섞여 잘리는 문제는 다른 실험(E2)에서 다룬다.
- 실제 단어 필터: wordfreq zipf_frequency 를 11개 언어에서 재고 최댓값을 쓴다(소문자 기준).
  zipf 3.0은 대략 백만 단어에 한 번, 2.0은 천만 단어에 한 번 나오는 빈도다.
  빈도는 결과에 영향을 주는 형태(어느 표기에서든 단일 토큰이거나 7종 모두 2토큰 이하인 형태)와
  형태 수 11,025개 이하인 모양의 모든 형태에 대해서만 잰다(시간 절약).

난수를 쓰지 않으므로 결과는 실행할 때마다 같다.
"""

from __future__ import annotations

import itertools
import json
import math
import multiprocessing
import os
import string
import time
from collections import Counter
from pathlib import Path

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")  # fork 뒤 HF tokenizers 경고를 끈다

from wordfreq import get_frequency_dict, zipf_frequency  # noqa: E402

from toklib import load_all  # noqa: E402

SEED = 20261007  # 난수를 쓰지 않지만 저장소 관례에 맞춰 둔다
VOWELS = "aeiou"
CONSONANTS = "".join(c for c in string.ascii_lowercase if c not in VOWELS)  # 21자, y 포함
WORD_LANGS = ["en", "es", "de", "fr", "it", "pt", "nl", "tr", "id", "pl", "sv"]
FILTERS = ["none", "lt3", "lt2"]  # 필터 없음, max zipf < 3.0, < 2.0
FILTER_CUT = {"none": math.inf, "lt3": 3.0, "lt2": 2.0}
SWEEP = [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, math.inf]  # zipf 기준을 바꿔 가며 센다 (inf = 필터 없음)
FULL_ZIPF_MAX_FORMS = 11025  # 이 이하 크기의 모양은 모든 형태의 빈도를 잰다
WORKERS = min(4, os.cpu_count() or 1)  # 측정 프로세스 수 (결과에는 영향 없음)

# 자음으로 시작하는 모양 = 어근 후보, 모음으로 시작하는 모양 = 문법 형태소 후보.
# 붙여 쓰기에서는 '다음 글자가 자음이면 어근, 모음이면 문법 형태'로 끊으므로 역할마다 모양 하나를 고른다.
ROOT_SHAPES = ["CV", "CVV", "CCV", "CVC", "CVCV", "CCVC", "CVCC", "CVCVC"]
GRAM_SHAPES = ["V", "VV", "VC", "VCV", "VCC", "VCVC"]
SHAPES = sorted(ROOT_SHAPES + GRAM_SHAPES, key=lambda s: (len(s), s))

# 표기 이름 → (문맥, 형태 → 표기 문자열)
VARIANTS = {
    "bare": ("1", lambda f: f),
    "space": ("the", lambda f: " " + f),
    "cap": ("1", lambda f: f.capitalize()),
    "space_cap": ("the", lambda f: " " + f.capitalize()),
}
VARIANT_LABEL = {"bare": "kat", "space": "␣kat", "cap": "Kat", "space_cap": "␣Kat"}

# 여러 토크나이저 합의 수준
LEVELS = ["all7", "no_sp", "ge6", "ge5", "claude", "le2_all7"]
LEVEL_LABEL = {
    "all7": "7종 모두",
    "no_sp": "mistral_sp 뺀 6종 모두",
    "ge6": "7종 중 6종 이상",
    "ge5": "7종 중 5종 이상",
    "claude": "claude_legacy 단독",
    "le2_all7": "7종 모두 2토큰 이하",
}
MAIN_LEVELS = ["all7", "no_sp", "ge6", "claude"]
TARGET_ROOTS, TARGET_GRAM = 1000, 100

OUT_DIR = Path(__file__).resolve().parent / "results"
NAMES: list[str] = []  # main() 에서 토크나이저 순서로 채운다


# ---------------------------------------------------------------- 측정

def expand(shape: str) -> list[str]:
    pools = [VOWELS if ch == "V" else CONSONANTS for ch in shape]
    return ["".join(p) for p in itertools.product(*pools)]


def span_count(tok, ctx: str, s: str) -> int:
    """문맥 ctx 뒤에 붙인 s 가 차지하는 토큰 수. 문맥과 한 토큰으로 합쳐지면 -1."""
    cut, pos, n = len(ctx), 0, 0
    for p in tok.pieces(ctx + s):
        start, pos = pos, pos + len(p)
        if start < cut < pos:
            return -1
        if start >= cut and p:
            n += 1
    return n


def word_freq(form: str) -> dict:
    """11개 언어 zipf 의 최댓값, 그 언어, 영어 zipf."""
    zs = [(zipf_frequency(form, lang), lang) for lang in WORD_LANGS]
    z, lang = max(zs, key=lambda x: x[0])
    return {"max": z, "lang": lang if z > 0 else None, "en": zs[0][0]}


def level_ok(c: tuple[int, ...], level: str) -> bool:
    """c = 토크나이저별 토큰 수 튜플 (NAMES 순서, -1 = 문맥과 합쳐짐)."""
    s = [x == 1 for x in c]
    if level == "all7":
        return all(s)
    if level == "no_sp":
        return all(x for x, n in zip(s, NAMES) if n != "mistral_sp")
    if level == "ge6":
        return sum(s) >= len(NAMES) - 1
    if level == "ge5":
        return sum(s) >= len(NAMES) - 2
    if level == "claude":
        return s[NAMES.index("claude_legacy")]
    if level == "le2_all7":
        return all(1 <= x <= 2 for x in c)
    raise ValueError(level)


def matters(c: tuple[int, ...]) -> bool:
    """이 형태가 어떤 집계에든 들어가는가 (단일 토큰이 하나라도 있거나 7종 모두 2토큰 이하)."""
    return any(x == 1 for x in c) or level_ok(c, "le2_all7")


_TOKS: dict = {}  # 작업 프로세스가 fork 로 물려받는 토크나이저


def _measure_chunk(args: tuple[str, list[str]]) -> tuple[dict, dict]:
    """형태 묶음 하나를 잰다. 작업 프로세스에서 돈다."""
    shape, forms = args
    counts = {var: [tuple(span_count(t, ctx, spell(f)) for t in _TOKS.values()) for f in forms]
              for var, (ctx, spell) in VARIANTS.items()}
    full = n_forms(shape) <= FULL_ZIPF_MAX_FORMS
    zipf = {f: word_freq(f) for i, f in enumerate(forms)
            if full or any(matters(counts[v][i]) for v in VARIANTS)}
    return counts, zipf


def n_forms(shape: str) -> int:
    return math.prod(len(VOWELS) if ch == "V" else len(CONSONANTS) for ch in shape)


def measure(toks: dict, workers: int = WORKERS, chunk: int = 8000) -> tuple[dict, dict]:
    """counts[shape][variant][form] = 토크나이저별 토큰 수 튜플, zipf[form] = word_freq(form).

    형태를 묶음으로 나눠 여러 프로세스(fork)에서 잰다. 묶음 순서대로 합치므로 결과는 프로세스 수와 무관하다.
    """
    _TOKS.update(toks)
    word_freq("kat")  # 빈도 목록을 미리 읽어 두면 작업 프로세스가 물려받는다
    jobs = [(shape, forms[i:i + chunk]) for shape in SHAPES for forms in [expand(shape)] for i in range(0, len(forms), chunk)]
    counts: dict = {shape: {var: {} for var in VARIANTS} for shape in SHAPES}
    zipf: dict = {}
    t0 = time.time()
    with multiprocessing.get_context("fork").Pool(workers) as pool:
        for (shape, forms), (c, z) in zip(jobs, pool.imap(_measure_chunk, jobs)):
            for var in VARIANTS:
                counts[shape][var].update(zip(forms, c[var]))
            zipf.update(z)
    for shape in SHAPES:
        print(f"  {shape:6} {n_forms(shape):>7,} forms")
    print(f"  measured in {time.time() - t0:.0f}s with {workers} processes")
    return counts, zipf


def sanity(toks: dict, counts: dict) -> dict:
    """(1) 문맥 측정값과 홀로 토큰화한 값(toklib is_single_token)의 단일 토큰 판정 차이 (CVC, VC 전체)
    (2) 모든 모양에서 문맥과 합쳐진 형태 수."""
    out: dict = {"context_vs_standalone_CVC_VC": {}, "merged_with_context_all_shapes": {}}
    for var, (_, spell) in VARIANTS.items():
        out["context_vs_standalone_CVC_VC"][var] = {}
        out["merged_with_context_all_shapes"][var] = {}
        for i, (name, t) in enumerate(toks.items()):
            diff = n = 0
            for shape in ["CVC", "VC"]:
                for f, c in counts[shape][var].items():
                    n += 1
                    diff += (c[i] == 1) != t.is_single_token(spell(f))
            out["context_vs_standalone_CVC_VC"][var][name] = {"forms": n, "single_token_disagree": diff}
            out["merged_with_context_all_shapes"][var][name] = sum(
                c[i] == -1 for shape in SHAPES for c in counts[shape][var].values())
    return out


# ---------------------------------------------------------------- 집계

def _mean(xs: list[int]) -> float | None:
    return round(sum(xs) / len(xs), 3) if xs else None



def aggregate(counts: dict, zipf: dict) -> tuple[dict, dict]:
    stats: dict = {}
    lists: dict = {}
    for shape in SHAPES:
        stats[shape], lists[shape] = {}, {}
        for var in VARIANTS:
            data = counts[shape][var]
            per_tok = {n: {flt: 0 for flt in FILTERS} for n in NAMES}
            agree = {lv: {flt: 0 for flt in FILTERS} for lv in LEVELS}
            sweep = {mode: {lv: [0] * len(SWEEP) for lv in LEVELS} for mode in ["max11", "en"]}
            odd = Counter()
            hist = Counter()
            excluded_lang = Counter()
            excluded_only_non_en = 0
            keep = {"all7": [], "no_sp": [], "ge6": []}
            for f, c in data.items():
                k = sum(x == 1 for x in c)
                hist[k] += 1
                if k == len(NAMES) - 1:
                    odd[NAMES[[x == 1 for x in c].index(False)]] += 1
                if not matters(c):
                    continue
                z = zipf[f]
                oks = {lv: level_ok(c, lv) for lv in LEVELS}
                for flt in FILTERS:
                    if z["max"] < FILTER_CUT[flt]:
                        for n, x in zip(NAMES, c):
                            per_tok[n][flt] += x == 1
                        for lv in LEVELS:
                            agree[lv][flt] += oks[lv]
                for j, cut in enumerate(SWEEP):
                    for lv in LEVELS:
                        if oks[lv]:
                            sweep["max11"][lv][j] += z["max"] < cut
                            sweep["en"][lv][j] += z["en"] < cut
                if oks["all7"] and z["max"] >= 3.0:
                    excluded_lang[z["lang"]] += 1
                    excluded_only_non_en += z["en"] < 3.0
                if z["max"] < 3.0:
                    for lv in keep:
                        if oks[lv]:
                            keep[lv].append([f, z["max"]])
            full = len(data) <= FULL_ZIPF_MAX_FORMS
            stats[shape][var] = {
                "n_forms": len(data),
                # 토큰화와 상관없이 단어 필터를 통과하는 형태 수 (모든 형태의 빈도를 잰 모양만)
                "n_pass_filter": {flt: (sum(zipf[f]["max"] < FILTER_CUT[flt] for f in data) if full else None)
                                  for flt in FILTERS},
                "per_tokenizer": per_tok,
                "agreement": agree,
                "zipf_sweep": {"cuts": [c if c != math.inf else None for c in SWEEP], **sweep},
                "n_tokenizers_single_hist": {str(k): hist[k] for k in range(len(NAMES) + 1)},
                "odd_one_out_in_6of7": {n: odd[n] for n in NAMES},
                "all7_excluded_by_lt3": {"by_lang": dict(sorted(excluded_lang.items(), key=lambda x: -x[1])),
                                         "en_below_3": excluded_only_non_en},
                "mean_tokens": {n: _mean([c[i] for c in data.values() if c[i] > 0]) for i, n in enumerate(NAMES)},
            }
            lists[shape][var] = {f"{lv}_lt3": v for lv, v in keep.items()}
    return stats, lists


def mechanism(counts: dict, zipf: dict) -> dict:
    """단일 토큰이 되는 토크나이저 수(k)별로 실제 단어(max zipf ≥ 3.0)의 비율. 모든 형태의 빈도를 잰 모양만."""
    out: dict = {}
    for shape in ["VC", "CV", "VCV", "CVC", "CCV", "CVCV"]:
        out[shape] = {}
        for var in ["bare", "space"]:
            rows = {}
            for k in range(len(NAMES) + 1):
                fs = [f for f, c in counts[shape][var].items() if sum(x == 1 for x in c) == k]
                if fs:
                    zs = [zipf[f]["max"] for f in fs]
                    rows[str(k)] = {"n": len(fs), "word_ge3_share": round(sum(z >= 3.0 for z in zs) / len(fs), 4),
                                    "word_ge2_share": round(sum(z >= 2.0 for z in zs) / len(fs), 4),
                                    "mean_max_zipf": round(sum(zs) / len(fs), 3)}
            out[shape][var] = rows
    return out


def fragment_sets(max_len: int = 5) -> tuple[set, set, int]:
    """11개 언어에서 zipf ≥ 3.0 인 단어들의 진부분 접두(prefix) 집합과 진부분 문자열(substring) 집합.

    zipf_frequency 와 같은 wordfreq 목록(best)을 쓴다. zipf ≥ 3.0 ⇔ 빈도 ≥ 1e-6.
    """
    words = set()
    for lang in WORD_LANGS:
        words.update(w.lower() for w, fr in get_frequency_dict(lang).items() if fr >= 1e-6)
    prefixes, subs = set(), set()
    for w in words:
        n = len(w)
        for k in range(1, min(max_len, n - 1) + 1):
            prefixes.add(w[:k])
            for i in range(n - k + 1):
                subs.add(w[i:i + k])
    return prefixes, subs, len(words)


def fragments(counts: dict, zipf: dict) -> dict:
    """단어 필터를 통과한(zipf < 3.0) 형태가 흔한 단어의 조각인 비율.

    ␣ 표기: 흔한 단어(zipf ≥ 3.0)의 진부분 접두인가 (예: ' calc' ← calculate)
    붙임 표기: 흔한 단어 안 어딘가에 들어 있는 진부분 문자열인가 (예: 'ated' ← created)
    7종 모두 단일 토큰인 형태와, 어느 토크나이저에서도 단일 토큰이 아닌 형태(기준선)를 비교한다.
    기준선은 모든 형태의 빈도를 잰 모양에서만 낸다.
    """
    prefixes, subs, n_words = fragment_sets()
    out: dict = {"n_frequent_words": n_words, "shapes": {}}
    for shape in ["VCV", "VCC", "VCVC", "CVC", "CCV", "CVCV", "CVCC", "CCVC", "CVCVC"]:
        full = len(counts[shape]["bare"]) <= FULL_ZIPF_MAX_FORMS
        out["shapes"][shape] = {}
        for var in ["bare", "space"]:
            pool = subs if var == "bare" else prefixes
            groups = {"all7": [], "none_single": []}
            for f, c in counts[shape][var].items():
                if f not in zipf or zipf[f]["max"] >= 3.0:
                    continue
                k = sum(x == 1 for x in c)
                if k == len(NAMES):
                    groups["all7"].append(f)
                elif k == 0 and full:
                    groups["none_single"].append(f)
            out["shapes"][shape][var] = {
                g: {"n": len(fs), "fragment_share": round(sum(f in pool for f in fs) / len(fs), 4) if fs else None,
                    "non_fragment_examples": [f for f in fs if f not in pool][:20]}
                for g, fs in groups.items() if g == "all7" or full}
    return out


def form_table(counts: dict, zipf: dict) -> dict:
    """형태별 상세: 어떤 표기에서든 한 토크나이저라도 단일 토큰인 형태만 싣는다."""
    out: dict = {}
    for shape in SHAPES:
        out[shape] = {}
        for f in counts[shape]["bare"]:
            per_var = {v: counts[shape][v][f] for v in VARIANTS}
            if not any(x == 1 for c in per_var.values() for x in c):
                continue
            out[shape][f] = {
                "zipf": zipf[f]["max"], "zipf_lang": zipf[f]["lang"], "zipf_en": zipf[f]["en"],
                "tokens": {v: "".join("x" if x < 0 else str(min(x, 9)) for x in c) for v, c in per_var.items()},
            }
    return out


def letter_productivity(counts: dict) -> dict:
    """글자별 생산성. 모양·표기·위치마다 그 글자를 포함한 형태의 단일 토큰 비율."""
    out: dict = {}
    for shape in ["CV", "VC", "CVC", "CCV", "CVCV"]:
        out[shape] = {}
        for var in VARIANTS:
            data = counts[shape][var]
            out[shape][var] = {}
            for pos, ch in enumerate(shape):
                key = f"{pos}{ch}"
                out[shape][var][key] = {}
                for L in (VOWELS if ch == "V" else CONSONANTS):
                    rows = [c for f, c in data.items() if f[pos] == L]
                    out[shape][var][key][L] = {
                        "n": len(rows),
                        "mean_rate": round(sum(sum(x == 1 for x in c) for c in rows) / (len(rows) * len(NAMES)), 4),
                        "ge6_rate": round(sum(level_ok(c, "ge6") for c in rows) / len(rows), 4),
                        "all7_rate": round(sum(level_ok(c, "all7") for c in rows) / len(rows), 4),
                        "per_tokenizer_rate": {n: round(sum(c[i] == 1 for c in rows) / len(rows), 4)
                                               for i, n in enumerate(NAMES)},
                    }
    return out


def reduce_consonants(counts: dict, zipf: dict, var: str, level: str) -> list[dict]:
    """CVC 어근에서 자음을 하나씩 빼는 탐욕 탐색.

    목표 = 해당 합의 수준에서 단일 토큰인 CVC 형태(단어 필터 없이, 토큰화만 본다).
    빼면 목표 형태를 가장 적게 잃는 자음부터 뺀다. 동률이면 알파벳 순으로 앞선 자음.
    """
    single = {f for f, c in counts["CVC"][var].items() if level_ok(c, level)}
    current = set(CONSONANTS)

    def n_in(fs: set, cs: set) -> int:
        return sum(1 for f in fs if f[0] in cs and f[2] in cs)

    lt3 = {f for f in single if zipf[f]["max"] < 3.0}
    steps = []
    removed = None
    while True:
        total = len(current) ** 2 * len(VOWELS)
        steps.append({"k": len(current), "removed": removed, "set": "".join(sorted(current)),
                      "single": n_in(single, current), "single_lt3": n_in(lt3, current), "total": total,
                      "yield": round(n_in(single, current) / total, 4)})
        if len(current) <= 5:
            break
        removed = min(sorted(current), key=lambda c: n_in(single, current) - n_in(single, current - {c}))
        current = current - {removed}
    return steps


def best_n(counts: dict, zipf: dict, shapes: list[str], var: str, n: int, flt: str) -> dict:
    """후보 풀에서 토큰 비용이 가장 낮은 n개를 고른다 (단어 필터 적용).

    순위: 단일 토큰이 아닌 토크나이저 수 → 7종 토큰 수 합 → 최대 토큰 수 → 알파벳.
    """
    def cost(c):
        cc = [9 if x < 0 else x for x in c]
        return (sum(x != 1 for x in cc), sum(cc), max(cc))

    cand = []
    for shape in shapes:
        for f, c in counts[shape][var].items():
            if f in zipf and zipf[f]["max"] < FILTER_CUT[flt]:
                cand.append((cost(c), f, c))
    cand.sort()
    pick = cand[:n]
    if not pick:
        return {"available": 0}
    return {
        "available": len(cand),
        "picked": len(pick),
        "all7_single": sum(level_ok(c, "all7") for _, _, c in pick),
        "no_sp_single": sum(level_ok(c, "no_sp") for _, _, c in pick),
        "le2_all7": sum(level_ok(c, "le2_all7") for _, _, c in pick),
        "mean_tokens": {nm: round(sum(c[i] for _, _, c in pick) / len(pick), 3) for i, nm in enumerate(NAMES)},
        "max_tokens": max(max(c) for _, _, c in pick),
        "last_picked": pick[-1][1],
    }


def designs(stats: dict, counts: dict, zipf: dict) -> dict:
    """핵심 질문: 어근 1,000개 + 문법 형태 100개를 채우는 모양·표기 조합이 있는가."""
    best: dict = {}
    for role, shapes in [("root", ROOT_SHAPES), ("gram", GRAM_SHAPES)]:
        best[role] = {}
        for var in VARIANTS:
            best[role][var] = {}
            for lv in LEVELS:
                best[role][var][lv] = {}
                for flt in FILTERS:
                    cand = sorted(((stats[s][var]["agreement"][lv][flt], s) for s in shapes), key=lambda x: (-x[0], x[1]))
                    best[role][var][lv][flt] = {"shape": cand[0][1], "count": cand[0][0], "all": {s: k for k, s in cand}}
    combos = {
        "glued": ("bare", "bare"),
        "glued_camel": ("cap", "cap"),
        "spaced": ("space", "space"),
        "wordspaced": ("space", "bare"),
        "wordspaced_cap": ("space_cap", "bare"),
    }
    out: dict = {"best_single_shape": best, "combos": {}, "pools_variable_length": {}, "best_n": {}}
    for name, (rv, gv) in combos.items():
        out["combos"][name] = {"root_variant": rv, "gram_variant": gv, "levels": {}}
        for lv in LEVELS:
            out["combos"][name]["levels"][lv] = {}
            for flt in FILTERS:
                r, g = best["root"][rv][lv][flt], best["gram"][gv][lv][flt]
                out["combos"][name]["levels"][lv][flt] = {
                    "root_shape": r["shape"], "roots": r["count"], "gram_shape": g["shape"], "gram": g["count"],
                    "meets": r["count"] >= TARGET_ROOTS and g["count"] >= TARGET_GRAM,
                }
    for var in VARIANTS:
        out["pools_variable_length"][var] = {}
        for role, shapes in [("root", ROOT_SHAPES), ("gram", GRAM_SHAPES)]:
            out["pools_variable_length"][var][role] = {
                lv: {flt: sum(stats[s][var]["agreement"][lv][flt] for s in shapes) for flt in FILTERS} for lv in LEVELS}
            out["pools_variable_length"][var][role]["per_tokenizer"] = {
                n: {flt: sum(stats[s][var]["per_tokenizer"][n][flt] for s in shapes) for flt in FILTERS} for n in NAMES}
    for var in VARIANTS:
        out["best_n"][var] = {}
        for role, shapes, n in [("root", ROOT_SHAPES, TARGET_ROOTS), ("gram", GRAM_SHAPES, TARGET_GRAM)]:
            for flt in ["lt3", "lt2"]:
                for sh in shapes + ["pool"]:
                    key = f"{role}:{sh}:{flt}"
                    out["best_n"][var][key] = best_n(counts, zipf, shapes if sh == "pool" else [sh], var, n, flt)
    return out


# ---------------------------------------------------------------- 보고서

def pct(x: float) -> str:
    return f"{100 * x:.0f}"


def md_table(header: list[str], rows: list[list], align: str | None = None) -> list[str]:
    align = align or ("l" + "r" * (len(header) - 1))
    sep = ["---:" if a == "r" else "---" for a in align]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(sep) + " |"]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return lines


COMBO_LABEL = {
    "glued": "붙여 쓰기",
    "glued_camel": "붙여 쓰기 + 형태소 첫 글자 대문자",
    "spaced": "형태소마다 띄우기",
    "wordspaced": "어근 앞만 띄우기 (문법 형태는 붙임)",
    "wordspaced_cap": "어근 앞 띄우기 + 대문자 (문법 형태는 붙임)",
}


def _examples(lists: dict, cands: list[tuple[str, str, str]]) -> str:
    """예시 형태가 실제로 7종 단일 & zipf < 3.0 목록에 있을 때만 예로 든다."""
    ok = [f"`{form}`" for shape, var, form in cands
          if form.strip() in {f for f, _ in lists[shape][var]["all7_lt3"]}]
    return f"({', '.join(ok)} 등)" if ok else ""


def key_answer(stats: dict, des: dict, mech: dict, frag: dict, lists: dict) -> list[str]:
    """핵심 답을 측정값에서 문장으로 만든다."""
    L: list[str] = []
    best = des["best_single_shape"]
    pools = des["pools_variable_length"]
    V = VARIANT_LABEL

    def top(role: str, lv: str, flt: str, variants=VARIANTS) -> tuple[int, str, str]:
        return max(((best[role][v][lv][flt]["count"], best[role][v][lv][flt]["shape"], v) for v in variants),
                   key=lambda x: (x[0], x[2] == "space", x[1]))

    # 1. 판정
    met = [(c, lv, flt) for c, d in des["combos"].items() for lv in ["all7", "no_sp", "ge6"] for flt in ["lt3", "lt2"]
           if d["levels"][lv][flt]["meets"]]
    if met:
        L.append("- **목표를 채우는 조합**: " + ", ".join(f"{COMBO_LABEL[c]} ({LEVEL_LABEL[lv]}, {flt})" for c, lv, flt in met))
    else:
        L.append(f"- **목표(어근 {TARGET_ROOTS:,} + 문법 {TARGET_GRAM}, 단일 토큰, 단어 필터 zipf < 3.0)를 채우는 모양·표기 조합은 없다.** "
                 "7종 모두, mistral_sp 뺀 6종, 7종 중 6종 이상 어느 기준에서도 없다. 막히는 쪽은 어근이다.")
    # 2. 문법 형태만
    g_ok = [(sh, v, flt, stats[sh][v]["agreement"]["all7"][flt]) for flt in ["lt3", "lt2"] for v in VARIANTS for sh in GRAM_SHAPES
            if stats[sh][v]["agreement"]["all7"][flt] >= TARGET_GRAM]
    if g_ok:
        L.append(f"- 문법 형태 {TARGET_GRAM}개는 7종 모두 단일 토큰으로 채울 수 있다: "
                 + ", ".join(f"{sh} {V[v]} {n:,}개 (zipf < {FILTER_CUT[flt]:.1f})" for sh, v, flt, n in g_ok)
                 + ". 모두 붙임 표기이므로 붙여 쓰기나 '어근 앞만 띄우기' 설계에 해당한다. "
                 "다만 이 형태들은 거의 모두 흔한 단어 안의 조각" + _examples(lists, [("VCVC", "bare", "ated"), ("VCVC", "bare", "atic"),
                                                                     ("VCC", "bare", "ity")]) + "이다(2.5절).")
    # 2-1. 기존 스케치 (docs/01: CVC 어근 + VC 접사, 붙여 쓰기)
    cb, vb = stats["CVC"]["bare"]["agreement"]["all7"], stats["VC"]["bare"]["agreement"]["all7"]
    L.append(f"- docs/01의 스케치(붙여 쓴 CVC 어근 + VC 접사)를 그대로 재면: CVC kat 7종 단일 {cb['none']:,} → zipf < 3.0 {cb['lt3']:,} → < 2.0 {cb['lt2']:,}, "
             f"VC kat 7종 단일 {vb['none']:,} → zipf < 3.0 {vb['lt3']:,} → < 2.0 {vb['lt2']:,}. "
             f"VC 105개 중 zipf < 3.0인 것은 토큰화와 상관없이 {stats['VC']['bare']['n_pass_filter']['lt3']:,}개뿐이다(두 글자 문자열은 거의 다 어느 언어에선가 단어·약어다).")
    # 3. 최대치
    for lv in ["all7", "no_sp"]:
        r = [top("root", lv, f) for f in FILTERS]
        L.append(f"- 어근 최대치 ({LEVEL_LABEL[lv]}, 모양 하나): 필터 없음 {r[0][0]:,} ({r[0][1]} {V[r[0][2]]}) → "
                 f"zipf < 3.0 {r[1][0]:,} ({r[1][1]} {V[r[1][2]]}) → zipf < 2.0 {r[2][0]:,} ({r[2][1]} {V[r[2][2]]}).")
    p = pools["space"]
    L.append(f"- 띄어 쓰는 설계에서 자음 시작 모양을 모두 합친 어근 풀(␣kat, 7종 모두 단일 토큰): 필터 없음 {p['root']['all7']['none']:,} → "
             f"zipf < 3.0 {p['root']['all7']['lt3']:,} → < 2.0 {p['root']['all7']['lt2']:,}. "
             f"단어 필터가 없으면 1,000을 넘지만 필터를 걸면 크게 모자란다.")
    # 4. 원인
    parts = []
    for var in ["space", "bare"]:
        m = mech["CVC"][var]
        hi, lo = m.get(str(len(NAMES))), m.get("0")
        if hi and lo:
            parts.append(f"CVC {V[var]}: 7종 모두 단일 토큰인 {hi['n']:,}개 중 {pct(hi['word_ge3_share'])}%, "
                         f"어느 토크나이저에서도 단일 토큰이 아닌 {lo['n']:,}개 중 {pct(lo['word_ge3_share'])}%")
    L.append("- 병목은 단어 필터다. 어느 언어에선가 zipf ≥ 3.0인 형태의 비율 — " + "; ".join(parts) + ". "
             "토크나이저가 한 토큰으로 만든 글자열은 원래 자주 나오는 글자열이므로, 단일 토큰일수록 실제 단어다(2.4절).")
    npf = stats["CVC"]["bare"]["n_pass_filter"]
    L.append(f"- CVC는 토큰화와 상관없이 2,205개 중 {npf['lt3']:,}개만 zipf < 3.0, {npf['lt2']:,}개만 zipf < 2.0이다. "
             f"CVC 하나로는 토큰 수를 따지기 전에 이미 1,000개 어근을 채울 수 없다.")
    # 5. 조각
    fs = frag["shapes"]
    items = []
    for shape, var in [("CVCC", "space"), ("CVCVC", "space"), ("VCVC", "bare"), ("CVC", "space")]:
        d = fs[shape][var]
        if d["all7"]["n"]:
            base = d.get("none_single")
            items.append(f"{shape} {V[var]} {pct(d['all7']['fragment_share'])}% ({d['all7']['n']:,}개 중)"
                         + (f", 기준선(단일 토큰 아님) {pct(base['fragment_share'])}%" if base and base["n"] else ""))
    non_frag = sorted({f for d in fs.values() for var in ["bare", "space"] for f in d[var]["all7"]["non_fragment_examples"]})
    L.append("- 필터를 통과한 단일 토큰도 대부분 흔한 단어의 조각이다"
             + _examples(lists, [("CVCC", "space", " calc"), ("CVCVC", "space", " gover"), ("VCVC", "bare", "ated")]) + ". "
             "흔한 단어의 진부분 접두(␣ 표기) 또는 진부분 문자열(붙임 표기)인 비율: " + "; ".join(items) + " (2.5절). "
             "조각이 아닌 7종 단일 형태는 " + (", ".join(f"`{f}`" for f in non_frag) or "없음") + "뿐이다(코드 식별자가 많다). "
             "zipf 필터는 '단어 그 자체'만 거르고 이런 조각이 끌고 오는 뜻은 거르지 못한다.")
    # 6. 타협
    bn = des["best_n"]
    t = []
    for var, key in [("space", "root:pool:lt3"), ("space", "root:CVCV:lt3"), ("bare", "root:CVCC:lt3")]:
        d = bn[var][key]
        if d.get("picked"):
            sh = key.split(":")[1]
            t.append(f"{'어근 풀(띄어 쓰기 전용)' if sh == 'pool' else sh} {V[var]}: 7종 단일 {d['all7_single']:,}개, 7종 모두 2토큰 이하 {d['le2_all7']:,}개, "
                     f"평균 토큰 o200k {d['mean_tokens']['o200k']:.2f} / claude_legacy {d['mean_tokens']['claude_legacy']:.2f} / "
                     f"mistral_sp {d['mean_tokens']['mistral_sp']:.2f}")
    L.append(f"- 타협 1 (2토큰 허용): zipf < 3.0을 지키며 토큰 비용이 가장 낮은 어근 {TARGET_ROOTS:,}개를 고르면 — " + "; ".join(t) + " (2.3절).")
    sw = stats["CVC"]["space"]["zipf_sweep"]
    j3, j4 = SWEEP.index(3.0), SWEEP.index(4.0)
    L.append(f"- 타협 2 (필터 완화): CVC ␣kat 7종 단일 토큰은 11개 언어 기준 zipf < 3.0에서 {sw['max11']['all7'][j3]:,}, < 4.0에서 "
             f"{sw['max11']['all7'][j4]:,}; 영어만 보면 < 3.0에서 {sw['en']['all7'][j3]:,}, < 4.0에서 {sw['en']['all7'][j4]:,}개다(2.1절). "
             "필터를 완화한다는 것은 실제 단어를 어근으로 쓰겠다는 뜻이다.")
    ex = stats["CVC"]["space"]["all7_excluded_by_lt3"]
    langs = ", ".join(f"{k} {v}" for k, v in list(ex["by_lang"].items())[:6])
    L.append(f"- CVC ␣kat 7종 단일 토큰 가운데 zipf ≥ 3.0으로 빠진 형태를 빈도가 가장 높은 언어로 나누면 {langs} … 이고, "
             f"그중 {ex['en_below_3']:,}개는 영어 zipf가 3.0 미만이다.")
    # 7. claude
    c_rn, c_r, c_g = top("root", "claude", "none"), top("root", "claude", "lt3"), top("gram", "claude", "lt3")
    pc = pools["space"]["root"]["per_tokenizer"]["claude_legacy"]
    worse = [n for n in NAMES if stats["CVC"]["space"]["per_tokenizer"][n]["none"] < stats["CVC"]["bare"]["per_tokenizer"][n]["none"]]
    L.append(f"- claude_legacy 단독: 어근(모양 하나) 필터 없음 최대 {c_rn[0]:,} ({c_rn[1]} {V[c_rn[2]]}), zipf < 3.0 최대 {c_r[0]:,} "
             f"({c_r[1]} {V[c_r[2]]}); ␣kat 어근 풀 zipf < 3.0 {pc['lt3']:,}개; 문법 형태 zipf < 3.0 최대 {c_g[0]:,} ({c_g[1]} {V[c_g[2]]}). "
             f"CVC에서 ␣kat 단일 토큰이 kat보다 적은 토크나이저: {', '.join(worse) or '없음'} "
             f"(claude_legacy ␣kat {stats['CVC']['space']['per_tokenizer']['claude_legacy']['none']:,} / kat {stats['CVC']['bare']['per_tokenizer']['claude_legacy']['none']:,}). "
             "나머지 토크나이저는 CVC에서 ␣kat 단일 토큰이 kat 이상이다.")
    return L


def write_md(path: Path, stats: dict, lists: dict, letters: dict, reduced: dict, des: dict, mech: dict,
             frag: dict, sanity_res: dict) -> None:
    L: list[str] = []
    a = L.append
    a("# E1. 형태소 후보 목록: 토큰 하나로 끝나는 형태는 몇 개인가")
    a("")
    a("`python3 inventory.py` 로 만든 결과다. 전체 수치와 형태 목록은 [inventory.json](inventory.json)에 있다. "
      "표기는 `kat`(붙임 소문자), `␣kat`(앞 공백), `Kat`(붙임 대문자 시작), `␣Kat`(앞 공백 + 대문자 시작)으로 적는다. "
      "'zipf < 3.0'은 11개 언어(" + ", ".join(WORD_LANGS) + ") 가운데 가장 높은 zipf 빈도가 3.0 미만이라는 뜻이다.")
    a("")

    # ---- 1. 핵심 답
    a("## 1. 핵심 질문에 대한 답")
    a("")
    a(f"질문: 어근 약 {TARGET_ROOTS:,}개와 문법 형태 약 {TARGET_GRAM}개를, 토크나이저 7종 모두(또는 mistral_sp만 빼고)에서 "
      "토큰 하나이면서 흔한 단어가 아닌 형태로 채울 수 있는 모양·표기가 있는가.")
    a("")
    L.extend(key_answer(stats, des, mech, frag, lists))
    a("")
    a("### 1.1 설계별 최대치 (모양 하나씩)")
    a("")
    a("어근은 자음 시작 모양(" + ", ".join(ROOT_SHAPES) + "), 문법 형태는 모음 시작 모양(" + ", ".join(GRAM_SHAPES) + ")에서 "
      "가장 많이 나오는 모양 하나를 고른다. 붙여 써도 '다음 글자가 자음이면 어근, 모음이면 문법 형태'로 끊을 수 있는 조건이다. "
      "칸 값은 `모양 개수`이고, 셋은 각각 `필터 없음 / zipf < 3.0 / zipf < 2.0`이다(필터마다 가장 많은 모양이 다를 수 있다).")
    a("")
    rows = []
    for cname, c in des["combos"].items():
        for lv in MAIN_LEVELS:
            d = c["levels"][lv]
            cell_r = " / ".join(f"{d[f]['root_shape']} {d[f]['roots']:,}" for f in FILTERS)
            cell_g = " / ".join(f"{d[f]['gram_shape']} {d[f]['gram']:,}" for f in FILTERS)
            rows.append([f"{COMBO_LABEL[cname]} ({VARIANT_LABEL[c['root_variant']]} + {VARIANT_LABEL[c['gram_variant']]})" if lv == "all7" else "",
                         LEVEL_LABEL[lv], cell_r, cell_g])
    L += md_table(["설계 (어근 표기 + 문법 표기)", "합의 수준", "어근", "문법 형태"], rows, "llll")
    a("")
    a("### 1.2 띄어 쓰는 설계: 길이가 다른 모양을 합친 풀")
    a("")
    a("공백이 경계를 알려 주므로 길이가 다른 모양을 섞어도 된다. 칸 값은 `필터 없음 / zipf < 3.0 / zipf < 2.0`이다.")
    a("")
    rows = []
    for var in ["space", "space_cap"]:
        p = des["pools_variable_length"][var]
        for lv in MAIN_LEVELS + ["le2_all7"]:
            rows.append([VARIANT_LABEL[var] if lv == "all7" else "", LEVEL_LABEL[lv],
                         " / ".join(f"{p['root'][lv][f]:,}" for f in FILTERS),
                         " / ".join(f"{p['gram'][lv][f]:,}" for f in FILTERS)])
    L += md_table(["표기", "합의 수준", "어근 풀", "문법 풀"], rows, "llrr")
    a("")

    a("### 1.3 토크나이저별 (zipf < 3.0, 단일 토큰)")
    a("")
    a("토크나이저 하나만 볼 때 단어 필터(zipf < 3.0)를 통과하는 단일 토큰 형태 수다. claude_legacy 행이 Claude 대용 지표다.")
    a("")
    cols = [("root", "space", None, "어근 풀 ␣kat"), ("root", "bare", "CVC", "CVC kat"), ("root", "space", "CVC", "CVC ␣kat"),
            ("root", "space", "CVCC", "CVCC ␣kat"), ("gram", "bare", "VCC", "VCC kat"), ("gram", "bare", "VCVC", "VCVC kat"),
            ("gram", "space", None, "문법 풀 ␣kat")]
    rows = []
    for n in NAMES:
        r = [n]
        for role, var, shape, _ in cols:
            if shape is None:
                r.append(f"{des['pools_variable_length'][var][role]['per_tokenizer'][n]['lt3']:,}")
            else:
                r.append(f"{stats[shape][var]['per_tokenizer'][n]['lt3']:,}")
        rows.append(r)
    L += md_table(["토크나이저"] + [c[3] for c in cols], rows)
    a("")

    # ---- 2. 타협
    a("## 2. 타협의 크기")
    a("")
    a("### 2.1 단어 필터 기준을 바꾸면")
    a("")
    a("7종 모두 단일 토큰인 형태 수. 위 줄은 11개 언어 최댓값 기준, 아래 줄(en)은 영어 zipf만 본 기준이다.")
    a("")
    cuts = ["< " + (f"{c:.1f}") if c != math.inf else "필터 없음" for c in SWEEP]
    rows = []
    for shape, var in [("VC", "bare"), ("VCV", "bare"), ("VCC", "bare"), ("VC", "space"), ("VCC", "space"),
                       ("CVC", "bare"), ("CVC", "space"), ("CCV", "space"), ("CVCV", "space"),
                       ("CCVC", "bare"), ("CVCC", "space"), ("CVCVC", "space")]:
        sw = stats[shape][var]["zipf_sweep"]
        rows.append([f"{shape} {VARIANT_LABEL[var]}", "11개 언어"] + [f"{x:,}" for x in sw["max11"]["all7"]])
        rows.append(["", "en"] + [f"{x:,}" for x in sw["en"]["all7"]])
    L += md_table(["모양 표기", "필터 언어"] + cuts, rows, "ll" + "r" * len(cuts))
    a("")
    a("### 2.2 단일 토큰 대신 '2토큰 이하'를 허용하면")
    a("")
    a("7종 모두에서 2토큰 이하인 형태 수 (`필터 없음 / zipf < 3.0 / zipf < 2.0`).")
    a("")
    rows = []
    for shape in ["VC", "VCV", "VCC", "CVC", "CCV", "CVCV", "CCVC", "CVCC"]:
        rows.append([shape] + [" / ".join(f"{stats[shape][v]['agreement']['le2_all7'][f]:,}" for f in FILTERS) for v in VARIANTS])
    L += md_table(["모양"] + [VARIANT_LABEL[v] for v in VARIANTS], rows, "lrrrr")
    a("")
    a(f"### 2.3 필터를 지키고 가장 싼 {TARGET_ROOTS:,}개 어근 / {TARGET_GRAM}개 문법 형태를 고르면")
    a("")
    a("단어 필터(zipf < 3.0)를 통과한 후보를 토큰 비용 순(단일 토큰이 아닌 토크나이저 수 → 7종 토큰 수 합)으로 정렬해 "
      f"어근 {TARGET_ROOTS:,}개, 문법 형태 {TARGET_GRAM}개를 고른 뒤 형태 하나당 평균 토큰 수를 쟀다. "
      "`풀`은 역할의 모든 모양을 합친 것으로 띄어 쓰는 설계에서만 쓸 수 있다. `후보`는 필터를 통과한 형태 수다"
      "(CCVC, CVCC, CVCVC는 빈도를 잰 형태, 즉 어디선가 단일 토큰이거나 7종 모두 2토큰 이하인 형태만 센다). "
      "오른쪽 일곱 칸은 고른 형태의 평균 토큰 수다.")
    a("")
    rows = []
    for var in ["bare", "space", "space_cap"]:
        for key in ["root:CVC:lt3", "root:CVCV:lt3", "root:CVCC:lt3", "root:CVCVC:lt3", "root:pool:lt3",
                    "gram:VC:lt3", "gram:VCV:lt3", "gram:VCC:lt3", "gram:VCVC:lt3", "gram:pool:lt3"]:
            d = des["best_n"][var][key]
            role, sh, _ = key.split(":")
            if not d.get("picked") or (sh == "pool" and not var.startswith("space")):
                continue  # 붙임 표기에서는 길이가 다른 모양을 섞으면 끊을 수 없다
            rows.append([VARIANT_LABEL[var], ("어근 " if role == "root" else "문법 ") + ("풀" if sh == "pool" else sh),
                         f"{d['available']:,}", f"{d['picked']:,}", f"{d['all7_single']:,}", f"{d['le2_all7']:,}"]
                        + [f"{d['mean_tokens'][n]:.2f}" for n in NAMES])
    L += md_table(["표기", "후보 풀", "후보", "고른 수", "7종 단일", "7종 ≤2"] + NAMES, rows, "ll" + "r" * (4 + len(NAMES)))
    a("")
    a("### 2.4 단일 토큰일수록 실제 단어다")
    a("")
    a("단일 토큰이 되는 토크나이저 수(k)별로 형태 수와 zipf ≥ 3.0인 비율(%)이다(`형태 수 (비율)`).")
    a("")
    rows = []
    for shape in ["VC", "VCV", "CVC", "CCV", "CVCV"]:
        for var in ["bare", "space"]:
            m = mech[shape][var]
            rows.append([f"{shape} {VARIANT_LABEL[var]}"] + [f"{m[str(k)]['n']:,} ({pct(m[str(k)]['word_ge3_share'])})" if str(k) in m else "-"
                                                           for k in range(len(NAMES) + 1)])
    L += md_table(["모양 표기"] + [f"k={k}" for k in range(len(NAMES) + 1)], rows)
    a("")

    a("### 2.5 필터를 통과한 단일 토큰은 대개 단어 조각이다")
    a("")
    a(f"11개 언어에서 zipf ≥ 3.0인 단어 {frag['n_frequent_words']:,}개(언어 간 중복 제거)를 모아, zipf < 3.0인 형태가 "
      "그 단어들의 진부분 접두(␣ 표기: 단어 첫머리 조각, 예 ` calc` ← calculate)이거나 "
      "진부분 문자열(붙임 표기: 단어 안 조각, 예 `ated` ← created)인 비율(%)을 쟀다. "
      "기준선은 같은 모양에서 어느 토크나이저에서도 단일 토큰이 아닌 형태다(모든 형태의 빈도를 잰 모양만).")
    a("")
    rows = []
    for shape, d in frag["shapes"].items():
        for var in ["bare", "space"]:
            x = d[var]
            base = x.get("none_single")
            rows.append([f"{shape} {VARIANT_LABEL[var]}",
                         f"{x['all7']['n']:,}", pct(x["all7"]["fragment_share"]) if x["all7"]["n"] else "-",
                         f"{base['n']:,}" if base else "-", pct(base["fragment_share"]) if base and base["n"] else "-",
                         " ".join(x["all7"]["non_fragment_examples"][:10]) or "-"])
    L += md_table(["모양 표기", "7종 단일 & < 3.0", "조각 %", "단일 아님 & < 3.0", "조각 %", "조각이 아닌 7종 단일 형태 (최대 10개)"],
                  rows, "lrrrrl")
    a("")

    # ---- 3. 측정 방법
    a("## 3. 측정 방법과 점검")
    a("")
    a("- 모음 V = aeiou, 자음 C = 나머지 21자(y 포함). 모양마다 가능한 형태를 모두 만들었다.")
    a("- 앞 공백 표기는 `the` 뒤에, 붙임 표기는 `1` 뒤에 붙여 토큰화하고, 문맥 뒤의 토큰 수를 셌다. "
      "문맥과 형태가 한 토큰으로 합쳐지면 단일 토큰이 아닌 것으로 쳤다.")
    a("  - 이유: mistral_sp(SentencePiece)는 입력 맨 앞에 가짜 공백을 붙인다. 그래서 `kat`을 홀로 재면 사실상 `␣kat`을, "
      "`␣kat`을 홀로 재면 공백 두 개짜리를 재게 된다. 문맥을 두면 문장 중간의 실제 모습을 잰다.")
    a("  - 붙임 표기 값은 '형태가 글자 덩어리의 맨 앞에 올 때'의 값이다. `katenmirob`처럼 글자가 이어질 때 "
      "이웃 글자와 섞여 잘리는 문제는 이 실험에서 재지 않았다(E2의 몫).")
    a("  - o200k, llama4, mistral_tekken은 사전 분할 정규식이 대문자 앞에서 끊으므로 `KatEnMirOb`의 각 형태소가 `Kat` 표기 값과 같은 조건에서 토큰화된다. "
      "cl100k, llama3, claude_legacy는 대소문자 경계에서 끊지 않는다.")
    a("- 단어 필터: wordfreq `zipf_frequency`를 11개 언어에서 재어 최댓값을 썼다. 대문자 표기도 소문자 형태의 빈도로 거른다.")
    a("- 합의 수준: " + ", ".join(f"`{LEVEL_LABEL[lv]}`" for lv in LEVELS) + ". `7종 중 6종 이상`은 어느 토크나이저가 빠져도 된다.")
    a("- claude_legacy는 Claude 2 시절 토크나이저다. 현행 Claude 토크나이저는 공개되지 않아 대용으로만 쓴다.")
    a("")
    a("**점검 1: CVC + VC 전체에서 문맥 측정과 홀로 측정의 단일 토큰 판정이 다른 형태 수**")
    a("")
    rows = [[VARIANT_LABEL[v]] + [f"{sanity_res['context_vs_standalone_CVC_VC'][v][n]['single_token_disagree']:,}" for n in NAMES]
            for v in VARIANTS]
    L += md_table(["표기"] + NAMES, rows)
    a("")
    a("**점검 2: 모든 모양에서 문맥 토큰과 합쳐진 형태 수** (0이면 문맥이 형태를 건드리지 않았다)")
    a("")
    rows = [[VARIANT_LABEL[v]] + [f"{sanity_res['merged_with_context_all_shapes'][v][n]:,}" for n in NAMES] for v in VARIANTS]
    L += md_table(["표기"] + NAMES, rows)
    a("")

    # ---- 4. 토크나이저별
    a("## 4. 모양·표기별 단일 토큰 수 (토크나이저별, 필터 없음)")
    a("")
    rows = []
    for shape in SHAPES:
        for var in VARIANTS:
            st = stats[shape][var]
            rows.append([shape if var == "bare" else "", VARIANT_LABEL[var], f"{st['n_forms']:,}"]
                        + [f"{st['per_tokenizer'][n]['none']:,}" for n in NAMES])
    L += md_table(["모양", "표기", "전체"] + NAMES, rows, "ll" + "r" * (1 + len(NAMES)))
    a("")

    a("## 5. 합의 수준 × 단어 필터")
    a("")
    a("칸 값은 `필터 없음 / zipf < 3.0 / zipf < 2.0` 순서다. `필터 통과`는 토큰화와 상관없이 단어 필터를 통과하는 형태 수다"
      "(빈도를 일부 형태만 잰 큰 모양은 `-`).")
    a("")
    rows = []
    for shape in SHAPES:
        for var in VARIANTS:
            ag = stats[shape][var]["agreement"]
            npf = stats[shape][var]["n_pass_filter"]
            passed = f"{npf['lt3']:,} / {npf['lt2']:,}" if npf["lt3"] is not None else "-"
            rows.append([shape if var == "bare" else "", VARIANT_LABEL[var], f"{stats[shape][var]['n_forms']:,}",
                         passed if var == "bare" else ""]
                        + [f"{ag[lv]['none']:,} / {ag[lv]['lt3']:,} / {ag[lv]['lt2']:,}" for lv in LEVELS])
    L += md_table(["모양", "표기", "전체", "필터 통과 (< 3.0 / < 2.0)"] + [LEVEL_LABEL[lv] for lv in LEVELS], rows,
                  "ll" + "r" * (2 + len(LEVELS)))
    a("")
    a("**7종 중 정확히 6종에서 단일 토큰인 형태에서 홀로 실패한 토크나이저** (필터 없음)")
    a("")
    rows = []
    for shape in ["CV", "VC", "VCV", "VCC", "CCV", "CVC", "CVCV", "CVCC"]:
        for var in VARIANTS:
            o = stats[shape][var]["odd_one_out_in_6of7"]
            rows.append([shape if var == "bare" else "", VARIANT_LABEL[var]] + [f"{o[n]:,}" for n in NAMES])
    L += md_table(["모양", "표기"] + NAMES, rows, "ll" + "r" * len(NAMES))
    a("")

    # ---- 6. 글자별 생산성
    a("## 6. 글자별 생산성")
    a("")
    a("CVC에서 그 자음이 첫 자리(C1) 또는 끝 자리(C2)에 올 때의 단일 토큰 비율(%)이다. "
      "`평균`은 7종의 단일 토큰 비율 평균, `6+`는 7종 중 6종 이상에서 단일 토큰인 비율, `claude`는 claude_legacy의 비율이다. "
      "C1 6+와 C2 6+의 합이 큰 순서로 정렬했다. 단어 필터는 걸지 않았다.")
    a("")
    for var in ["space", "bare"]:
        cv = letters["CVC"][var]
        a(f"**CVC {VARIANT_LABEL[var]}**")
        a("")
        order = sorted(CONSONANTS, key=lambda c: (-(cv["0C"][c]["ge6_rate"] + cv["2C"][c]["ge6_rate"]), c))
        rows = [[c, pct(cv["0C"][c]["mean_rate"]), pct(cv["0C"][c]["ge6_rate"]),
                 pct(cv["0C"][c]["per_tokenizer_rate"]["claude_legacy"]),
                 pct(cv["2C"][c]["mean_rate"]), pct(cv["2C"][c]["ge6_rate"]),
                 pct(cv["2C"][c]["per_tokenizer_rate"]["claude_legacy"])] for c in order]
        L += md_table(["자음", "C1 평균", "C1 6+", "C1 claude", "C2 평균", "C2 6+", "C2 claude"], rows)
        a("")
    a("**모음** (CVC는 가운데 모음, VC·CV는 그 모음을 포함한 형태의 7종 중 6종 이상 단일 토큰 비율 %)")
    a("")
    cs, cb = letters["CVC"]["space"], letters["CVC"]["bare"]
    rows = [[v, pct(cs["1V"][v]["mean_rate"]), pct(cs["1V"][v]["ge6_rate"]), pct(cb["1V"][v]["mean_rate"]), pct(cb["1V"][v]["ge6_rate"]),
             pct(letters["VC"]["bare"]["0V"][v]["ge6_rate"]), pct(letters["VC"]["space"]["0V"][v]["ge6_rate"]),
             pct(letters["CV"]["bare"]["1V"][v]["ge6_rate"]), pct(letters["CV"]["space"]["1V"][v]["ge6_rate"])] for v in VOWELS]
    L += md_table(["모음", "CVC␣ 평균", "CVC␣ 6+", "CVC 평균", "CVC 6+", "VC 6+", "VC␣ 6+", "CV 6+", "CV␣ 6+"], rows)
    a("")
    a("**VC / CV 의 자음** (7종 중 6종 이상 단일 토큰 비율 %, 100이 아닌 자음만)")
    a("")
    rows = []
    for c in CONSONANTS:
        vals = [letters["VC"]["bare"]["1C"][c]["ge6_rate"], letters["VC"]["space"]["1C"][c]["ge6_rate"],
                letters["CV"]["bare"]["0C"][c]["ge6_rate"], letters["CV"]["space"]["0C"][c]["ge6_rate"]]
        if any(v < 1 for v in vals):
            rows.append([c] + [pct(v) for v in vals])
    L += md_table(["자음", "VC", "VC␣", "CV", "CV␣"], rows)
    a("")
    cs_ = letters["CVC"]["space"]
    score = {c: (cs_["0C"][c]["ge6_rate"] + cs_["2C"][c]["ge6_rate"]) / 2 for c in CONSONANTS}
    ranked = sorted(CONSONANTS, key=lambda c: (-score[c], c))
    v_rate = {v: cs_["1V"][v]["ge6_rate"] for v in VOWELS}
    vr = sorted(VOWELS, key=lambda v: (-v_rate[v], v))
    drop = [c for c in CONSONANTS if cs_["0C"][c]["ge6_rate"] - cs_["2C"][c]["ge6_rate"] >= 0.2]
    a(f"CVC ␣kat에서 6+ 비율(C1, C2 평균)이 높은 자음은 {', '.join(f'{c} {pct(score[c])}%' for c in ranked[:6])}, "
      f"낮은 자음은 {', '.join(f'{c} {pct(score[c])}%' for c in ranked[-6:])}이다. "
      f"모음은 {', '.join(f'{v} {pct(v_rate[v])}%' for v in vr)} 순이다. "
      f"끝 자리(C2)의 6+ 비율이 첫 자리(C1)보다 20%p 이상 낮은 자음: {', '.join(drop) or '없음'}.")
    a("")
    a("토크나이저별 글자 비율은 inventory.json 의 `letters`에 있다.")
    a("")

    # ---- 7. 축소 자음 집합
    a("## 7. 자음 집합 줄이기")
    a("")
    a("CVC에서 해당 합의 수준의 단일 토큰 형태(단어 필터 없이)를 가장 적게 잃는 자음부터 하나씩 뺐다. "
      "`수율`은 남은 자음으로 만들 수 있는 CVC 전체 가운데 단일 토큰 형태의 비율, `그중 < 3.0`은 단어 필터를 통과하는 수다.")
    a("")
    for key, steps in reduced.items():
        a(f"**{key}**")
        a("")
        rows = [[s["k"], s["removed"] or "-", f"{s['single']:,}", f"{s['total']:,}", pct(s["yield"]), f"{s['single_lt3']:,}"]
                for s in steps if s["k"] >= 10]
        L += md_table(["자음 수", "뺀 자음", "단일 토큰", "CVC 전체", "수율 %", "그중 < 3.0"], rows)
        a("")
    a("**제안 (기준: 단일 토큰 형태를 95% 이상 남기는 가장 작은 집합)**")
    a("")
    for key, steps in reduced.items():
        full = steps[0]
        s = [x for x in steps if x["single"] >= 0.95 * full["single"]][-1]
        gone = "".join(sorted(set(CONSONANTS) - set(s["set"])))
        a(f"- {key}: 자음 {s['k']}개 `{s['set']}` (뺀 자음 `{gone or '-'}`) → 단일 토큰 {s['single']:,}/{full['single']:,}, "
          f"수율 {pct(full['yield'])}% → {pct(s['yield'])}%, 단어 필터 통과 {full['single_lt3']:,} → {s['single_lt3']:,}")
    a("")
    a("자음을 줄여도 단일 토큰 형태의 절대 개수는 늘지 않는다. 형태를 목록에서 고른다면 축소는 개수 면에서 이득이 없고, "
      "이득은 사양을 짧게 쓰는 것과 붙여 쓴 문자열에서 경계가 덜 흔들릴 가능성(E2에서 확인할 것)뿐이다.")
    a("")

    # ---- 8. 목록 미리 보기
    a("## 8. 형태 목록 미리 보기")
    a("")
    a("전체 목록은 inventory.json 의 `lists`(모양 → 표기 → `all7_lt3`, `no_sp_lt3`, `ge6_lt3`, 항목은 [형태, max zipf])에 있다. "
      "아래는 알파벳 순 앞의 40개다.")
    a("")
    for shape, var, lv in [("VC", "bare", "all7"), ("VCV", "bare", "all7"), ("VCC", "bare", "all7"), ("VCVC", "bare", "all7"),
                           ("CVC", "bare", "all7"), ("CVC", "space", "all7"), ("CVC", "space", "no_sp"),
                           ("CVCC", "space", "all7"), ("CCVC", "bare", "all7"), ("CVCVC", "space", "all7")]:
        items = [f for f, _ in lists[shape][var][f"{lv}_lt3"]]
        a(f"- {shape} {VARIANT_LABEL[var]}, {LEVEL_LABEL[lv]}, zipf < 3.0 ({len(items)}개): " + (" ".join(items[:40]) or "없음"))
    a("")

    a("## 9. 한계")
    a("")
    a("- 현행 Claude 토크나이저는 공개되지 않았다. claude_legacy 결과가 현행 Claude에 그대로 적용된다는 보장은 없다.")
    a("- 단일 토큰 여부만 쟀다. 붙여 쓴 문자열 안에서 형태소 경계와 토큰 경계가 맞는지는 재지 않았다(E2).")
    a("- 단어 필터는 11개 언어의 빈도만 본다. 한국어·일본어·중국어 로마자 표기, 약어, 상표, 프로그래밍 식별자와의 겹침은 걸러지지 않는다.")
    a("- wordfreq는 짧은 글자열에 약어·이름·다른 언어 조각의 빈도까지 잡는다. 그래서 짧은 모양일수록 필터에서 많이 빠지고, "
      "zipf ≥ 3.0이라고 해서 그 형태가 모두 LLM에게 강한 뜻을 가진다는 보장도 없다. 실제 의미 간섭의 크기는 모델 API 없이 잴 수 없다.")
    a("- 단일 토큰이라도 그 토큰이 학습 데이터에서 특정 의미(이름, 약어, 코드 조각)에 묶여 있을 수 있다. 이 역시 이 실험으로는 잴 수 없다.")
    path.write_text("\n".join(L) + "\n")


def main() -> None:
    t0 = time.time()
    toks = load_all()
    NAMES.extend(toks)
    print("measuring ...")
    counts, zipf = measure(toks)
    print("aggregating ...")
    stats, lists = aggregate(counts, zipf)
    sanity_res = sanity(toks, counts)
    mech = mechanism(counts, zipf)
    frag = fragments(counts, zipf)
    letters = letter_productivity(counts)
    reduced = {}
    for var in ["space", "bare"]:
        for lv in ["no_sp", "ge6"]:
            reduced[f"CVC {VARIANT_LABEL[var]}, {LEVEL_LABEL[lv]}"] = reduce_consonants(counts, zipf, var, lv)
    des = designs(stats, counts, zipf)
    forms = form_table(counts, zipf)
    meta = {
        "experiment": "E1 morpheme inventory",
        "seed": SEED,
        "vowels": VOWELS,
        "consonants": CONSONANTS,
        "shapes": SHAPES,
        "root_shapes": ROOT_SHAPES,
        "gram_shapes": GRAM_SHAPES,
        "variants": {v: {"example": VARIANT_LABEL[v], "context": ctx} for v, (ctx, _) in VARIANTS.items()},
        "tokenizers": {n: {"description": t.description, "vocab_size": t.vocab_size} for n, t in toks.items()},
        "word_langs": WORD_LANGS,
        "filters": {"none": "필터 없음", "lt3": "max zipf < 3.0", "lt2": "max zipf < 2.0"},
        "levels": LEVEL_LABEL,
        "targets": {"roots": TARGET_ROOTS, "gram": TARGET_GRAM},
        "n_forms_with_zipf": len(zipf),
        "notes": [
            "토큰 수는 문맥 뒤에 붙여 잰 값이다. 앞 공백 표기는 'the' 뒤, 붙임 표기는 '1' 뒤.",
            "forms 의 tokens 문자열은 meta.tokenizers 순서대로 토크나이저별 토큰 수다 (9 이상은 9, x = 문맥과 합쳐짐).",
            "forms 에는 어떤 표기에서든 한 토크나이저라도 단일 토큰인 형태만 싣는다. 나머지는 모든 토크나이저·표기에서 2토큰 이상이다.",
            "lists 의 항목은 [형태(소문자), max zipf] 이고 max zipf < 3.0 인 것만 싣는다. 표기는 meta.variants 로 만든다.",
            "zipf 는 단일 토큰이 하나라도 있거나 7종 모두 2토큰 이하인 형태, 그리고 형태 수 11,025개 이하 모양의 모든 형태에 대해서만 쟀다.",
            "designs.best_n 의 키는 '역할:모양:필터' 이고 모양 'pool' 은 그 역할의 모든 모양을 합친 것이다.",
        ],
    }
    result = {"meta": meta, "sanity": sanity_res, "stats": stats, "designs": des, "mechanism": mech, "fragments": frag,
              "letters": letters, "reduced_consonants": reduced, "lists": lists, "forms": forms}
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "inventory.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))
    write_md(OUT_DIR / "inventory.md", stats, lists, letters, reduced, des, mech, frag, sanity_res)
    print(f"saved to {OUT_DIR} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
