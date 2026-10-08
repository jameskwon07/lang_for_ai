"""E2 경계 정렬: 표기 방식에 따라 토큰 경계가 형태소 경계와 얼마나 맞는가.

같은 합성 메시지(형태소 20~40개, 300개)를 여러 표기 방식과 형태 목록(인벤토리)으로 적은 뒤,
7개 토크나이저로 메시지 전체를 토큰화해서 형태소 경계와 토큰 경계를 비교한다.

인벤토리 (어근 CVC, 접사 VC. 자음 21자, 모음 aeiou)
- naive        : 단어 필터만 통과한 무작위 형태
- token_picked : 앞 공백 형태(" kat")가 7개 중 6개 이상 토크나이저에서 토큰 1개인 형태만
- bare_picked  : (보조) 공백 없는 형태("kat")가 바이트 BPE 6개 중 5개 이상에서 토큰 1개인 형태만.
                 붙여 쓰기(W1)에 유리한 형태를 골랐을 때의 최선값을 보려고 추가했다.

단어 필터: 11개 언어(wordfreq) 최대 zipf < 3. 단, VC 접사는 이 기준을 통과하는 형태가 1개뿐이어서
접사에는 zipf < 4.5 를 쓴다 (두 기준의 풀 크기를 모두 결과에 기록한다).

SentencePiece(mistral_sp)는 입력 앞에 가짜 공백(▁)을 스스로 붙이므로 " kat"을 넣으면 "▁" + "▁kat" 두 조각이 된다.
그래서 mistral_sp의 "앞 공백 형태"는 "kat"을 넣어 잰다 (문장 안의 "▁kat"과 같은 조각).
같은 이유로 mistral_sp의 "공백 없는 형태"는 toklib 으로 따로 잴 수 없어 bare_picked 기준에서 뺀다.

표기 방식 (예: kat-en mir-ob, 단어 2개)
- W1 nospace     : katenmirob      모두 붙여 쓴다
- W2 spaced      : kat en mir ob   형태소마다 띄운다
- W3 wordspaced  : katen mirob     단어마다 띄운다
- W4 camel       : KatEnMirOb      띄우지 않고 형태소마다 첫 글자 대문자
- W5 wordcamel   : KatEn MirOb     단어마다 띄우고, 형태소마다 첫 글자 대문자
- W6 lowercamel  : katEn mirOb     (추가) 단어마다 띄우고, 단어의 첫 형태소는 소문자, 나머지는 첫 글자 대문자
- W7 rootcamel   : KatenMirob      (추가) 띄우지 않고 어근만 첫 글자 대문자 (대문자로 공백을 대신할 수 있는가)

경계 규칙: 공백은 뒤 형태소에 속한다 (" en"). 모든 토크나이저가 공백을 뒤 단어에 붙이기 때문이다.
따라서 공백 앞 위치가 형태소 경계이고, 공백이 따로 토큰이 되면 정밀도가 떨어진다.

지표 (토크나이저 × 표기 × 인벤토리, 모든 메시지를 합쳐 계산)
- tokens_per_morpheme : 토큰 수 / 형태소 수
- chars_per_token     : 글자 수(공백 포함) / 토큰 수
- recall              : 형태소 경계 중 토큰 경계이기도 한 비율 (메시지 양 끝 제외)
- precision           : 토큰 경계 중 형태소 경계이기도 한 비율 (메시지 양 끝 제외)
- one_token_share     : 메시지 안에서 정확히 토큰 1개인 형태소의 비율 (앞 공백 포함)

사용법
    python3 alignment.py      # results/alignment.json, results/alignment.md 생성
"""

from __future__ import annotations

import json
import random
import statistics
import time
from pathlib import Path

from wordfreq import zipf_frequency

from toklib import load_all

SEED = 20261007
VOWELS = "aeiou"
CONSONANTS = "bcdfghjklmnpqrstvwxyz"  # 21자 (y 포함)
WORD_LANGS = ["en", "es", "de", "fr", "it", "pt", "nl", "tr", "id", "pl", "sv"]
ROOT_MAX_ZIPF = 3.0
AFFIX_MAX_ZIPF = 4.5  # 3.0 이면 VC 접사가 1개만 남는다
ZIPF_REPORT_THRESHOLDS = [3.0, 3.5, 4.0, 4.5, 5.0]
PICK_MIN = 6  # token_picked: 7개 중
BARE_MIN = 5  # bare_picked: 바이트 BPE 6개 중
SP_NAME = "mistral_sp"

N_MESSAGES = 300
MIN_MORPH, MAX_MORPH = 20, 40
N_DRAWS = 5  # 인벤토리마다 어휘(형태 배정)를 몇 번 새로 뽑는가
ZIPF_S = 1.0  # 어근·접사 사용 빈도 = 순위^-s

# 메시지 골격: 술어 단어 + 논항 단어 1~3개 (+ 수식어 단어)
PRED_AFFIX_P = [0.10, 0.25, 0.35, 0.20, 0.10]  # 접사 0~4개
ARG_AFFIX_P = [0.35, 0.50, 0.15]  # 접사 0~2개
MOD_AFFIX_P = [0.70, 0.30]  # 접사 0~1개
COMPOUND_P = {"pred": 0.10, "arg": 0.15, "mod": 0.0}  # 어근 2개(합성어)일 확률
N_ARGS_P = [0.30, 0.45, 0.25]  # 논항 1~3개
MOD_P = 0.30  # 논항 뒤에 수식어 단어가 붙을 확률

INVENTORIES = ["naive", "token_picked", "bare_picked"]
INV_LABEL = {"naive": "naive (무작위)", "token_picked": "token-picked (앞 공백 1토큰)",
             "bare_picked": "bare-picked (보조, 붙여 쓴 형태 1토큰)"}
DESIGNS = {
    "W1_nospace": "모두 붙여 쓴다",
    "W2_spaced": "형태소마다 띄운다",
    "W3_wordspaced": "단어마다 띄우고 단어 안은 붙인다",
    "W4_camel": "띄우지 않고 형태소마다 첫 글자 대문자",
    "W5_wordcamel": "단어마다 띄우고 형태소마다 첫 글자 대문자",
    "W6_lowercamel": "(추가) 단어마다 띄우고 단어의 첫 형태소만 소문자, 나머지는 첫 글자 대문자",
    "W7_rootcamel": "(추가) 띄우지 않고 어근만 첫 글자 대문자",
}
WORD_SPACED = {"W3_wordspaced", "W5_wordcamel", "W6_lowercamel"}

# 통과 기준: 형태소 = 토큰
STRICT = {"recall": 0.95, "precision": 0.95, "tpm": 1.05}
LOOSE = {"recall": 0.90, "precision": 0.90, "tpm": 1.10}

OUT_DIR = Path(__file__).resolve().parent / "results"


# ---------------------------------------------------------------- 형태 풀

def max_zipf(form: str) -> float:
    return max(zipf_frequency(form, lang) for lang in WORD_LANGS)


def lead_space_single(tok, form: str) -> bool:
    """문장 안에서 앞에 공백이 붙은 형태(" kat")가 토큰 1개인가."""
    return tok.count(form if tok.name == SP_NAME else " " + form) == 1


def bare_single(tok, form: str) -> bool | None:
    """공백 없는 형태("kat")가 토큰 1개인가. mistral_sp 는 잴 수 없어 None."""
    return None if tok.name == SP_NAME else tok.count(form) == 1


def build_pools(toks: dict) -> tuple[dict, dict]:
    """인벤토리별 (어근 풀, 접사 풀)과 풀 크기 보고용 표를 만든다."""
    cvc = [a + v + b for a in CONSONANTS for v in VOWELS for b in CONSONANTS]
    vc = [v + c for v in VOWELS for c in CONSONANTS]
    mz = {f: max_zipf(f) for f in cvc + vc}
    n_lead = {f: sum(lead_space_single(t, f) for t in toks.values()) for f in cvc + vc}
    n_bare = {f: sum(bool(bare_single(t, f)) for t in toks.values()) for f in cvc + vc}

    def pick(forms, th, rule):
        return sorted(f for f in forms if mz[f] < th and rule(f))

    rules = {"naive": lambda f: True, "token_picked": lambda f: n_lead[f] >= PICK_MIN,
             "bare_picked": lambda f: n_bare[f] >= BARE_MIN}
    pools = {inv: {"roots": pick(cvc, ROOT_MAX_ZIPF, r), "affixes": pick(vc, AFFIX_MAX_ZIPF, r)}
             for inv, r in rules.items()}
    by_threshold = {inv: {str(th): {"roots_cvc": len(pick(cvc, th, r)), "affixes_vc": len(pick(vc, th, r))}
                          for th in ZIPF_REPORT_THRESHOLDS}
                    for inv, r in rules.items()}
    # 단어 필터를 통과한 형태를, 앞 공백 형태가 1토큰인 토크나이저 수(0~7)별로 센다
    lead_hist = {
        "roots_cvc": {n: sum(1 for f in cvc if mz[f] < ROOT_MAX_ZIPF and n_lead[f] == n) for n in range(8)},
        "affixes_vc": {n: sum(1 for f in vc if mz[f] < AFFIX_MAX_ZIPF and n_lead[f] == n) for n in range(8)},
    }
    report = {
        "candidates": {"cvc": len(cvc), "vc": len(vc)},
        "root_max_zipf": ROOT_MAX_ZIPF, "affix_max_zipf": AFFIX_MAX_ZIPF,
        "pool_sizes": {inv: {k: len(v) for k, v in p.items()} for inv, p in pools.items()},
        "pool_sizes_by_zipf_threshold": by_threshold,
        "word_filtered_forms_by_n_lead_space_single": lead_hist,
        "token_picked_roots": pools["token_picked"]["roots"],
        "token_picked_affixes": pools["token_picked"]["affixes"],
    }
    return pools, report


def isolated_rates(toks: dict, pools: dict) -> dict:
    """풀 안 형태를 하나씩 따로 넣었을 때 토큰 1개인 비율 (문맥 없는 참고값)."""
    out = {}
    for inv, p in pools.items():
        forms = p["roots"] + p["affixes"]
        out[inv] = {}
        for name, t in toks.items():
            bare = [bare_single(t, f) for f in forms]
            bare_cap = [bare_single(t, f.capitalize()) for f in forms]
            out[inv][name] = {
                "lead_space": _share(lead_space_single(t, f) for f in forms),
                "lead_space_cap": _share(lead_space_single(t, f.capitalize()) for f in forms),
                "bare": None if bare[0] is None else _share(bare),
                "bare_cap": None if bare_cap[0] is None else _share(bare_cap),
            }
    return out


def _share(bools) -> float:
    bools = list(bools)
    return round(sum(bools) / len(bools), 4) if bools else 0.0


# ---------------------------------------------------------------- 메시지 골격

def zipf_cum(n: int) -> list[float]:
    acc, out = 0.0, []
    for r in range(n):
        acc += 1.0 / (r + 1) ** ZIPF_S
        out.append(acc)
    return out


def make_word(rng: random.Random, kind: str, root_cum, affix_cum) -> list[tuple[str, int]]:
    """단어 = 어근 1~2개 + 접사 0~4개. 형태소는 (종류 'R'/'A', 순위)."""
    n_roots = 2 if rng.random() < COMPOUND_P[kind] else 1
    p = {"pred": PRED_AFFIX_P, "arg": ARG_AFFIX_P, "mod": MOD_AFFIX_P}[kind]
    n_aff = rng.choices(range(len(p)), weights=p)[0]
    roots = rng.choices(range(len(root_cum)), cum_weights=root_cum, k=n_roots)
    affixes: set[int] = set()
    while len(affixes) < n_aff:  # 한 단어 안에서 접사는 겹치지 않는다
        affixes.add(rng.choices(range(len(affix_cum)), cum_weights=affix_cum)[0])
    # 접사 순서는 고정 슬롯 순서(순위 순)로 둔다
    return [("R", r) for r in roots] + [("A", a) for a in sorted(affixes)]


def make_sentence(rng: random.Random, root_cum, affix_cum) -> list[list[tuple[str, int]]]:
    words = [make_word(rng, "pred", root_cum, affix_cum)]
    for _ in range(rng.choices([1, 2, 3], weights=N_ARGS_P)[0]):
        words.append(make_word(rng, "arg", root_cum, affix_cum))
        if rng.random() < MOD_P:
            words.append(make_word(rng, "mod", root_cum, affix_cum))
    return words


def make_skeletons(rng: random.Random, n_roots: int, n_affixes: int) -> list[list[list[tuple[str, int]]]]:
    """형태소 MIN_MORPH~MAX_MORPH 개인 메시지 골격 N_MESSAGES 개. 모든 인벤토리·표기가 같은 골격을 쓴다."""
    root_cum, affix_cum = zipf_cum(n_roots), zipf_cum(n_affixes)
    out = []
    while len(out) < N_MESSAGES:
        target = rng.randint(MIN_MORPH, MAX_MORPH)
        words: list = []
        while sum(len(w) for w in words) < target:
            words += make_sentence(rng, root_cum, affix_cum)
        if MIN_MORPH <= sum(len(w) for w in words) <= MAX_MORPH:
            out.append(words)
    return out


# ---------------------------------------------------------------- 표기

def render(words: list[list[tuple[str, str]]], design: str) -> tuple[str, list[tuple[int, int, str, bool]]]:
    """(종류, 형태) 단어 목록 → (문자열, 형태소 구간 목록). 구간 = (시작, 끝, 종류, 단어 첫 형태소인가).
    앞 공백은 뒤 형태소 구간에 포함한다."""
    parts, spans, pos = [], [], 0
    for word in words:
        for mi, (kind, form) in enumerate(word):
            spaced = pos > 0 and (design == "W2_spaced" or (mi == 0 and design in WORD_SPACED))
            if design in ("W4_camel", "W5_wordcamel"):
                s = form.capitalize()
            elif design == "W6_lowercamel":
                s = form if mi == 0 else form.capitalize()
            elif design == "W7_rootcamel":
                s = form.capitalize() if kind == "R" else form
            else:
                s = form
            chunk = (" " if spaced else "") + s
            spans.append((pos, pos + len(chunk), kind, mi == 0))
            parts.append(chunk)
            pos += len(chunk)
    return "".join(parts), spans


# ---------------------------------------------------------------- 측정

COUNTERS = ["tokens", "chars", "morphs", "mb", "tb", "hit", "mb_word", "hit_word", "mb_inner", "hit_inner",
            "one", "one_R", "one_A", "n_R", "n_A", "lead", "one_lead", "space_only"]


def measure(tok, text: str, spans, acc: dict) -> int:
    pieces = tok.pieces(text)
    bounds = [0]
    for p in pieces:
        bounds.append(bounds[-1] + len(p))
    assert bounds[-1] == len(text), (tok.name, text, pieces)
    tb = set(bounds)
    inner_tb = tb - {0, len(text)}
    acc["tokens"] += len(pieces)
    acc["chars"] += len(text)
    acc["morphs"] += len(spans)
    acc["tb"] += len(inner_tb)
    acc["space_only"] += sum(1 for p in pieces if p.strip() == "")
    for i, (s, e, kind, word_initial) in enumerate(spans):
        if i > 0:
            hit = s in tb
            acc["mb"] += 1
            acc["hit"] += hit
            key = "word" if word_initial else "inner"
            acc["mb_" + key] += 1
            acc["hit_" + key] += hit
        one = s in tb and e in tb and not any(b in tb for b in range(s + 1, e))
        acc["one"] += one
        acc["one_" + kind] += one
        acc["n_" + kind] += 1
        if text[s] == " ":
            acc["lead"] += 1
            acc["one_lead"] += one
    return len(pieces)


def summarize(acc: dict) -> dict:
    def r(a, b):
        return round(a / b, 4) if b else None

    return {
        "tokens_per_morpheme": r(acc["tokens"], acc["morphs"]),
        "chars_per_token": r(acc["chars"], acc["tokens"]),
        "recall": r(acc["hit"], acc["mb"]),
        "precision": r(acc["hit"], acc["tb"]),
        "recall_word_boundary": r(acc["hit_word"], acc["mb_word"]),
        "recall_inner_boundary": r(acc["hit_inner"], acc["mb_inner"]),
        "one_token_share": r(acc["one"], acc["morphs"]),
        "one_token_share_root": r(acc["one_R"], acc["n_R"]),
        "one_token_share_affix": r(acc["one_A"], acc["n_A"]),
        "one_token_share_lead_space": r(acc["one_lead"], acc["lead"]),
        "space_only_tokens_per_space": r(acc["space_only"], acc["lead"]),
        "tokens_total": acc["tokens"],
        "morphemes_total": acc["morphs"],
        "chars_total": acc["chars"],
    }


def passes(m: dict, crit: dict) -> bool:
    return (m["recall"] >= crit["recall"] and m["precision"] >= crit["precision"]
            and m["tokens_per_morpheme"] <= crit["tpm"])


# ---------------------------------------------------------------- 실행

def run() -> tuple[dict, dict]:
    t_start = time.time()
    toks = load_all()
    pools, pool_report = build_pools(toks)
    n_roots = min(len(p["roots"]) for p in pools.values())
    n_affixes = min(len(p["affixes"]) for p in pools.values())
    pool_report["lexicon_size_used"] = {"roots": n_roots, "affixes": n_affixes,
                                        "note": "모든 인벤토리가 같은 크기의 어휘를 쓴다 (가장 작은 풀에 맞춤)"}
    pool_report["isolated_single_token_rates"] = isolated_rates(toks, pools)

    skeletons = make_skeletons(random.Random(SEED), n_roots, n_affixes)
    n_morph = [sum(len(w) for w in m) for m in skeletons]
    n_aff = sum(1 for m in skeletons for w in m for k, _ in w if k == "A")
    n_words = [len(m) for m in skeletons]
    n_compound = sum(1 for m in skeletons for w in m if sum(k == "R" for k, _ in w) == 2)
    skeleton_stats = {
        "messages": len(skeletons), "morphemes_total": sum(n_morph),
        "morphemes_per_message": {"min": min(n_morph), "max": max(n_morph), "mean": round(statistics.mean(n_morph), 2)},
        "words_per_message_mean": round(statistics.mean(n_words), 2),
        "affix_share": round(n_aff / sum(n_morph), 4),
        "compound_word_share": round(n_compound / sum(n_words), 4),
        "affixes_per_word_mean": round(n_aff / sum(n_words), 3),
    }

    acc = {(inv, d, t): dict.fromkeys(COUNTERS, 0) for inv in INVENTORIES for d in DESIGNS for t in toks}
    per_draw = {(inv, d, t): [] for inv in INVENTORIES for d in DESIGNS for t in toks}
    examples = {}
    for ii, inv in enumerate(INVENTORIES):
        for draw in range(N_DRAWS):
            rng = random.Random(SEED + 1000 * (ii + 1) + draw)
            roots = rng.sample(pools[inv]["roots"], n_roots)
            affixes = rng.sample(pools[inv]["affixes"], n_affixes)
            msgs = [[[(k, roots[i] if k == "R" else affixes[i]) for k, i in w] for w in m] for m in skeletons]
            if draw == 0:
                examples[inv] = msgs[0][:3]
            for d in DESIGNS:
                rendered = [render(m, d) for m in msgs]
                for name, t in toks.items():
                    a = acc[(inv, d, name)]
                    before_t, before_m = a["tokens"], a["morphs"]
                    for text, spans in rendered:
                        measure(t, text, spans, a)
                    per_draw[(inv, d, name)].append(round((a["tokens"] - before_t) / (a["morphs"] - before_m), 4))

    rows = []
    for (inv, d, name), a in acc.items():
        m = summarize(a)
        m.update(inventory=inv, design=d, tokenizer=name,
                 tokens_per_morpheme_by_draw=per_draw[(inv, d, name)],
                 pass_strict=passes(m, STRICT), pass_loose=passes(m, LOOSE))
        rows.append(m)

    # W2 와 W1 의 메시지당 토큰 차이 (공백이 공짜인가)
    idx = {(r["inventory"], r["design"], r["tokenizer"]): r for r in rows}
    space_cost = {inv: {name: {
        "w2_tokens_per_message": round(idx[(inv, "W2_spaced", name)]["tokens_total"] / (N_MESSAGES * N_DRAWS), 2),
        "w1_tokens_per_message": round(idx[(inv, "W1_nospace", name)]["tokens_total"] / (N_MESSAGES * N_DRAWS), 2),
        "w2_lead_space_morpheme_one_token": idx[(inv, "W2_spaced", name)]["one_token_share_lead_space"],
        "w2_space_only_tokens_per_space": idx[(inv, "W2_spaced", name)]["space_only_tokens_per_space"],
    } for name in toks} for inv in INVENTORIES}

    # 예시 (draw 0, 첫 메시지의 앞 3단어)
    ex_out = {}
    for inv, words in examples.items():
        ex_out[inv] = {}
        for d in DESIGNS:
            text, _ = render(words, d)
            ex_out[inv][d] = {"text": text, "pieces": {name: t.pieces(text) for name, t in toks.items()}}

    meta = {
        "experiment": "E2 boundary alignment",
        "seed": SEED, "n_draws": N_DRAWS, "zipf_s": ZIPF_S,
        "tokenizers": {name: t.description for name, t in toks.items()},
        "designs": DESIGNS,
        "pass_criteria": {"strict": STRICT, "loose": LOOSE},
        "skeleton_params": {"pred_affix_p": PRED_AFFIX_P, "arg_affix_p": ARG_AFFIX_P, "mod_affix_p": MOD_AFFIX_P,
                            "compound_p": COMPOUND_P, "n_args_p": N_ARGS_P, "mod_p": MOD_P},
        "skeleton_stats": skeleton_stats,
        "runtime_sec": None,
    }
    result = {"meta": meta, "pools": pool_report, "results": rows, "space_cost_w2": space_cost, "examples": ex_out}
    meta["runtime_sec"] = round(time.time() - t_start, 1)
    return result, toks


# ---------------------------------------------------------------- 요약 문서

def _f(x, nd=2):
    return "-" if x is None else f"{x:.{nd}f}"


def _pct(x):
    return "-" if x is None else f"{100 * x:.0f}%"


def write_markdown(res: dict, tok_names: list[str], path: Path) -> None:
    rows = res["results"]
    idx = {(r["inventory"], r["design"], r["tokenizer"]): r for r in rows}
    meta, pools = res["meta"], res["pools"]
    st = meta["skeleton_stats"]
    designs = list(DESIGNS)
    L: list[str] = []
    w = L.append

    def mean_over_toks(inv, d, key):
        vals = [idx[(inv, d, t)][key] for t in tok_names]
        return statistics.mean(vals)

    def n_pass(inv, d, kind):
        return sum(idx[(inv, d, t)]["pass_" + kind] for t in tok_names)

    def tok_per_msg(inv, d, t=None):
        names = [t] if t else tok_names
        return statistics.mean(idx[(inv, d, n)]["tokens_total"] for n in names) / (N_MESSAGES * N_DRAWS)

    def draw_range(inv, d):
        """추첨별 토큰/형태소(토크나이저 평균)의 최솟값, 최댓값."""
        per = [statistics.mean(idx[(inv, d, t)]["tokens_per_morpheme_by_draw"][k] for t in tok_names)
               for k in range(N_DRAWS)]
        return min(per), max(per)

    def tpr(inv, d, t):
        r = idx[(inv, d, t)]
        return f"{_f(r['tokens_per_morpheme'])}, R {_f(r['recall'])}, P {_f(r['precision'])}"

    sc = res["space_cost_w2"]
    chars_w1 = idx[("naive", "W1_nospace", tok_names[0])]["chars_total"] / (N_MESSAGES * N_DRAWS)
    chars_w2 = idx[("naive", "W2_spaced", tok_names[0])]["chars_total"] / (N_MESSAGES * N_DRAWS)

    w("# E2 경계 정렬: 표기 방식별 형태소·토큰 경계 일치")
    w("")
    w("`alignment.py` 가 만든 요약이다. 숫자는 모두 이 스크립트로 잰 값이며, 원자료는 `alignment.json` 에 있다.")
    w("")

    # 0. 요약 (숫자는 모두 계산값에서 가져온다)
    w("## 0. 요약")
    w("")
    best = max(((inv, d) for inv in INVENTORIES for d in designs),
               key=lambda k: (n_pass(*k, "strict"), n_pass(*k, "loose"), -mean_over_toks(*k, "tokens_per_morpheme")))
    b_inv, b_d = best
    ok = [t for t in tok_names if idx[(b_inv, b_d, t)]["pass_strict"]]
    bad = [t for t in tok_names if not idx[(b_inv, b_d, t)]["pass_strict"]]
    all7 = [k for k in ((inv, d) for inv in INVENTORIES for d in designs) if n_pass(*k, "strict") == len(tok_names)]
    naive_max = max(n_pass("naive", d, "loose") for d in designs)
    lo_ok = _f(min(idx[(b_inv, b_d, t)]["tokens_per_morpheme"] for t in ok))
    hi_ok = _f(max(idx[(b_inv, b_d, t)]["tokens_per_morpheme"] for t in ok))
    w(f"1. **형태소 = 토큰에 가장 가까운 조합은 `{b_d}` + {b_inv}** 이다. 엄격 기준을 {len(ok)}/{len(tok_names)}개 토크나이저"
      f"({', '.join(ok)})에서 통과했다 (토큰/형태소 {lo_ok if lo_ok == hi_ok else lo_ok + '~' + hi_ok}). "
      f"통과하지 못한 토크나이저: " + "; ".join(f"{t} ({tpr(b_inv, b_d, t)})" for t in bad) + ".")
    naive_txt = ("naive 인벤토리는 어떤 표기에서도 느슨한 기준조차 통과한 토크나이저가 없다." if naive_max == 0 else
                 f"naive 인벤토리는 어떤 표기에서도 느슨한 기준을 통과한 토크나이저가 최대 {naive_max}개다.")
    w(f"   - 7개 모두를 통과한 조합은 {'없다' if not all7 else ', '.join(f'{d}+{inv}' for inv, d in all7)}. " + naive_txt)
    w("   - 즉 표기만으로는 형태소 = 토큰이 되지 않는다. 앞 공백 형태가 1토큰인 형태를 골라야 하고, "
      "형태소마다 띄어 써야(W2) 고른 형태가 문맥 안에서도 그대로 1토큰으로 남는다.")
    tp_free = [t for t in tok_names if sc["token_picked"][t]["w2_lead_space_morpheme_one_token"] >= 0.95]
    tp_diff = [sc["token_picked"][t]["w2_tokens_per_message"] - sc["token_picked"][t]["w1_tokens_per_message"]
               for t in tp_free]
    nv_share = [sc["naive"][t]["w2_lead_space_morpheme_one_token"] for t in tok_names]
    space_only_all = max(sc[inv][t]["w2_space_only_tokens_per_space"] for inv in INVENTORIES for t in tok_names)
    space_txt = ("공백만으로 된 토큰은 어느 토크나이저·인벤토리에서도 하나도 생기지 않았다. " if space_only_all == 0 else
                 f"공백만으로 된 토큰이 공백 1개당 최대 {space_only_all:.3f}개 생겼다. ")
    w("2. **W2 의 공백**: " + space_txt +
      f"token-picked 형태에서는 \" kat\" 이 문맥 안에서 1토큰인 비율이 95% 이상인 토크나이저가 "
      f"{len(tp_free)}개({', '.join(tp_free)})이고, 이들에서 W2 는 W1 보다 메시지당 "
      f"{-max(tp_diff):.1f}~{-min(tp_diff):.1f} 토큰 **적다**. 공백이 공짜인 정도를 넘어 오히려 토큰을 줄인다.")
    for t in [t for t in tok_names if t not in tp_free]:
        c = sc["token_picked"][t]
        w(f"   - {t}: 1토큰 비율 {_pct(c['w2_lead_space_morpheme_one_token'])}, "
          f"W2 − W1 = {c['w2_tokens_per_message'] - c['w1_tokens_per_message']:+.1f} 토큰/메시지 → 공짜가 아니다.")
    w(f"   - naive 형태에서는 1토큰 비율이 {_pct(min(nv_share))}~{_pct(max(nv_share))} 로 공짜가 아니다.")
    w1 = {inv: (mean_over_toks(inv, "W1_nospace", "recall"), mean_over_toks(inv, "W1_nospace", "precision"),
                mean_over_toks(inv, "W1_nospace", "one_token_share"),
                mean_over_toks(inv, "W1_nospace", "one_token_share_root"),
                mean_over_toks(inv, "W1_nospace", "one_token_share_affix")) for inv in INVENTORIES}
    w("3. **붙여 쓰기(W1)의 비용**: 토큰 수는 인벤토리에 따라 W2 보다 많기도 적기도 하지만, "
      "경계 어긋남은 어느 인벤토리에서나 비슷하게 크다. (토크나이저 평균)")
    for inv in INVENTORIES:
        rr, pp, one, one_r, one_a = w1[inv]
        others = {d: tok_per_msg(inv, d) for d in designs}
        cheapest = min(others, key=others.get)
        rel = 100 * (others["W1_nospace"] / others["W2_spaced"] - 1)
        w(f"   - {inv}: recall {_f(rr)}, precision {_f(pp)}, 1토큰 형태소 {_pct(one)} (어근 {_pct(one_r)}, 접사 {_pct(one_a)}). "
          f"메시지당 토큰 W1 {others['W1_nospace']:.1f} / W2 {others['W2_spaced']:.1f} (W1 이 W2 보다 {rel:+.0f}%), "
          f"가장 적은 표기는 {cheapest} ({others[cheapest]:.1f}).")
    w("   - 붙여 쓰면 BPE 가 어근 첫 자음을 떼어 내거나(`mab`+`ef` → `m|ab|ef`) 어근 끝 자음을 뒤 접사와 묶는다"
      "(`mul`+`ox` → `mu|lox`, claude_legacy). 그래서 어근이 특히 많이 쪼개진다. 붙여 쓴 형태 기준으로 골라도(bare-picked) "
      f"recall 은 {_f(w1['bare_picked'][0])} 에 머문다.")
    w(f"   - 글자 수는 W1 {chars_w1:.1f}, W2 {chars_w2:.1f} 글자/메시지로 공백이 글자를 {100 * (chars_w2 / chars_w1 - 1):.0f}% 늘리지만, "
      "토큰 수와는 별개다.")
    cam = [idx[(inv, d, t)] for inv in INVENTORIES for d in ("W4_camel", "W5_wordcamel") for t in tok_names]
    w(f"4. **대문자 표기(W4, W5)**: 대문자가 토큰 경계를 만들어 recall 은 {_f(min(r['recall'] for r in cam))}~"
      f"{_f(max(r['recall'] for r in cam))} 로 높지만, 대문자로 시작하는 형태는 1토큰이 아닌 경우가 많아"
      f"(`G|id`) 토큰/형태소 {_f(min(r['tokens_per_morpheme'] for r in cam))}~{_f(max(r['tokens_per_morpheme'] for r in cam))}, "
      f"precision {_f(min(r['precision'] for r in cam))}~{_f(max(r['precision'] for r in cam))} 이다. "
      "추가한 W6(lowercamel, token-picked)은 느슨한 기준만 "
      + ", ".join(f"{t} ({tpr('token_picked', 'W6_lowercamel', t)})" for t in tok_names
                  if idx[("token_picked", "W6_lowercamel", t)]["pass_loose"])
      + " 에서 통과했다.")
    ps = pools["pool_sizes"]["token_picked"]
    hist = pools["word_filtered_forms_by_n_lead_space_single"]
    w(f"5. **형태 풀이 병목이다.** 단어 필터(zipf < {ROOT_MAX_ZIPF})를 통과한 CVC 중 token-picked 어근은 {ps['roots']}개"
      f"(7개 모두에서 1토큰은 {hist['roots_cvc'][7]}개)로, 문서의 목표 어근 수 500~1,000개에 크게 못 미친다. "
      f"필터를 zipf < 4.0 으로 풀면 {pools['pool_sizes_by_zipf_threshold']['token_picked']['4.0']['roots_cvc']}개다. "
      "VC 접사는 zipf < 3 을 통과하는 형태가 1개뿐이라 접사 필터를 완화했다.")
    w("")
    w("## 1. 설정")
    w("")
    w(f"- 합성 메시지 {st['messages']}개, 형태소 {st['morphemes_per_message']['min']}~{st['morphemes_per_message']['max']}개 "
      f"(평균 {st['morphemes_per_message']['mean']}), 단어 평균 {st['words_per_message_mean']}개, "
      f"접사 비율 {_pct(st['affix_share'])}, 합성어(어근 2개) 비율 {_pct(st['compound_word_share'])}.")
    w("- 메시지 = 문장(술어 단어 + 논항 단어 1~3개 + 가끔 수식어 단어)의 연속. 어근·접사 사용 빈도는 순위^-1 (Zipf).")
    w(f"- 모든 인벤토리와 표기가 **같은 골격**을 쓰고 형태만 바꾼다. 인벤토리마다 어휘(형태 배정)를 {meta['n_draws']}번 새로 뽑아 합산했다.")
    lex = pools["lexicon_size_used"]
    w(f"- 어휘 크기: 어근 {lex['roots']}개, 접사 {lex['affixes']}개 (세 인벤토리 공통, 가장 작은 풀에 맞춤).")
    w("- 경계 규칙: 공백은 뒤 형태소에 속한다. 공백이 따로 토큰이 되면 정밀도가 떨어진다.")
    w("- mistral_sp 의 \"앞 공백 형태\"는 `kat` 을 넣어 잰다 (SentencePiece 가 스스로 `▁` 를 붙이므로 `▁kat` 과 같다).")
    w("")
    w("### 형태 풀 크기")
    w("")
    w("| 인벤토리 | 어근 CVC | 접사 VC | 선정 기준 |")
    w("|---|---:|---:|---|")
    crit = {"naive": "단어 필터만",
            "token_picked": f"앞 공백 형태가 7개 중 {PICK_MIN}개 이상에서 1토큰",
            "bare_picked": f"붙여 쓴 형태가 바이트 BPE 6개 중 {BARE_MIN}개 이상에서 1토큰 (mistral_sp 제외)"}
    for inv in INVENTORIES:
        ps = pools["pool_sizes"][inv]
        w(f"| {INV_LABEL[inv]} | {ps['roots']} | {ps['affixes']} | {crit[inv]} |")
    w("")
    w(f"후보: CVC {pools['candidates']['cvc']}개, VC {pools['candidates']['vc']}개. "
      f"단어 필터 = 11개 언어 최대 zipf < {ROOT_MAX_ZIPF} (어근), < {AFFIX_MAX_ZIPF} (접사).")
    w("")
    w("**접사 필터를 완화한 이유**: zipf < 3 을 VC 에 그대로 쓰면 남는 접사가 거의 없다. 기준별 풀 크기(어근 / 접사):")
    w("")
    ths = [str(t) for t in ZIPF_REPORT_THRESHOLDS]
    w("| 인벤토리 | " + " | ".join(f"zipf < {t}" for t in ths) + " |")
    w("|---|" + "---:|" * len(ths))
    for inv in INVENTORIES:
        bt = pools["pool_sizes_by_zipf_threshold"][inv]
        w(f"| {inv} | " + " | ".join(f"{bt[t]['roots_cvc']} / {bt[t]['affixes_vc']}" for t in ths) + " |")
    w("")
    w("token-picked 어근은 엄격한 필터(zipf < 3)에서 "
      f"{pools['pool_sizes']['token_picked']['roots']}개뿐이다. 문서의 목표 어근 수(500~1,000개)에 크게 못 미친다.")
    w("")

    # 2. 핵심 답
    w("## 2. 핵심 결과: 형태소 = 토큰을 가장 많은 토크나이저에서 만족하는 표기")
    w("")
    w(f"통과 기준(엄격): recall ≥ {STRICT['recall']}, precision ≥ {STRICT['precision']}, 토큰/형태소 ≤ {STRICT['tpm']}. "
      f"느슨: {LOOSE['recall']} / {LOOSE['precision']} / {LOOSE['tpm']}. 셀 = 통과한 토크나이저 수 (엄격 / 느슨, 7개 중).")
    w("")
    w("| 표기 | " + " | ".join(INVENTORIES) + " |")
    w("|---|" + "---:|" * len(INVENTORIES))
    for d in designs:
        w(f"| {d} | " + " | ".join(f"{n_pass(inv, d, 'strict')} / {n_pass(inv, d, 'loose')}" for inv in INVENTORIES) + " |")
    w("")
    w("### 토크나이저 평균 (7개 단순 평균)")
    w("")
    for inv in INVENTORIES:
        w(f"**{INV_LABEL[inv]}**")
        w("")
        w("| 표기 | 토큰/형태소 | 추첨 간 범위 | 글자/토큰 | recall | precision | 1토큰 형태소 | 메시지당 글자 | 메시지당 토큰 |")
        w("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for d in designs:
            chars = idx[(inv, d, tok_names[0])]["chars_total"] / (N_MESSAGES * N_DRAWS)
            toks_msg = statistics.mean(idx[(inv, d, t)]["tokens_total"] for t in tok_names) / (N_MESSAGES * N_DRAWS)
            lo, hi = draw_range(inv, d)
            w(f"| {d} | {_f(mean_over_toks(inv, d, 'tokens_per_morpheme'))} | {_f(lo)}~{_f(hi)} | {_f(mean_over_toks(inv, d, 'chars_per_token'))} | "
              f"{_f(mean_over_toks(inv, d, 'recall'))} | {_f(mean_over_toks(inv, d, 'precision'))} | "
              f"{_pct(mean_over_toks(inv, d, 'one_token_share'))} | {chars:.1f} | {toks_msg:.1f} |")
        w("")

    # 3. 토크나이저별 표
    w("## 3. 토크나이저별 결과")
    w("")
    header = "| 표기 | " + " | ".join(tok_names) + " |"
    sep = "|---|" + "---:|" * len(tok_names)
    for inv in INVENTORIES:
        w(f"### {INV_LABEL[inv]}")
        w("")
        w("토큰/형태소 (어휘 5회 추첨 사이 최솟값~최댓값은 json 의 `tokens_per_morpheme_by_draw`)")
        w("")
        w(header)
        w(sep)
        for d in designs:
            w(f"| {d} | " + " | ".join(_f(idx[(inv, d, t)]["tokens_per_morpheme"]) for t in tok_names) + " |")
        w("")
        w("recall / precision")
        w("")
        w(header)
        w(sep)
        for d in designs:
            w(f"| {d} | " + " | ".join(f"{_f(idx[(inv, d, t)]['recall'])} / {_f(idx[(inv, d, t)]['precision'])}"
                                     for t in tok_names) + " |")
        w("")
        w("정확히 1토큰인 형태소 비율")
        w("")
        w(header)
        w(sep)
        for d in designs:
            w(f"| {d} | " + " | ".join(_pct(idx[(inv, d, t)]["one_token_share"]) for t in tok_names) + " |")
        w("")

    # 4. 공백은 공짜인가
    w("## 4. W2 의 공백은 공짜인가")
    w("")
    w("셀 = 앞 공백이 붙은 형태소(\" kat\")가 문맥 안에서 정확히 1토큰인 비율 / 공백만으로 된 토큰 수(공백 1개당) / "
      "메시지당 토큰 W2 − W1 / 판정. 판정은 1토큰 비율 95% 이상이고 공백 토큰이 없으면 \"공짜\".")
    w("")
    w("| 토크나이저 | " + " | ".join(INVENTORIES) + " |")
    w("|---|" + "---|" * len(INVENTORIES))
    for t in tok_names:
        cells = []
        for inv in INVENTORIES:
            c = sc[inv][t]
            diff = c["w2_tokens_per_message"] - c["w1_tokens_per_message"]
            free = c["w2_lead_space_morpheme_one_token"] >= 0.95 and c["w2_space_only_tokens_per_space"] == 0
            cells.append(f"{_pct(c['w2_lead_space_morpheme_one_token'])} / {_f(c['w2_space_only_tokens_per_space'], 3)} / "
                         f"{diff:+.1f} / {'공짜' if free else '아님'}")
        w(f"| {t} | " + " | ".join(cells) + " |")
    w("")
    w("문맥 없이 형태 하나씩 잰 1토큰 비율 (풀 전체, 앞 공백 소문자 / 앞 공백 대문자 시작 / 붙여 쓴 소문자 / 붙여 쓴 대문자 시작):")
    w("")
    w("| 토크나이저 | " + " | ".join(INVENTORIES) + " |")
    w("|---|" + "---|" * len(INVENTORIES))
    iso = pools["isolated_single_token_rates"]
    for t in tok_names:
        w(f"| {t} | " + " | ".join(
            f"{_pct(iso[inv][t]['lead_space'])} / {_pct(iso[inv][t]['lead_space_cap'])} / "
            f"{_pct(iso[inv][t]['bare'])} / {_pct(iso[inv][t]['bare_cap'])}" for inv in INVENTORIES) + " |")
    w("")
    w("mistral_sp 의 붙여 쓴 형태는 toklib 으로 따로 잴 수 없어 `-` 로 둔다.")
    w("")

    # 5. 붙여 쓰기 비용
    w("## 5. 붙여 쓰기(W1)의 실제 비용")
    w("")
    w("경계 종류별 recall (토크나이저 평균): 단어 경계 / 단어 안 형태소 경계.")
    w("")
    w("| 표기 | " + " | ".join(INVENTORIES) + " |")
    w("|---|" + "---|" * len(INVENTORIES))
    for d in designs:
        w(f"| {d} | " + " | ".join(
            f"{_f(mean_over_toks(inv, d, 'recall_word_boundary'))} / {_f(mean_over_toks(inv, d, 'recall_inner_boundary'))}"
            for inv in INVENTORIES) + " |")
    w("")
    w("정확히 1토큰인 형태소 비율 (토크나이저 평균): 어근 / 접사.")
    w("")
    w("| 표기 | " + " | ".join(INVENTORIES) + " |")
    w("|---|" + "---|" * len(INVENTORIES))
    for d in designs:
        w(f"| {d} | " + " | ".join(
            f"{_pct(mean_over_toks(inv, d, 'one_token_share_root'))} / {_pct(mean_over_toks(inv, d, 'one_token_share_affix'))}"
            for inv in INVENTORIES) + " |")
    w("")
    w("W1 대비 메시지당 토큰 비율 (토크나이저 평균, 1 미만이면 W1 보다 적다):")
    w("")
    w("| 표기 | " + " | ".join(INVENTORIES) + " |")
    w("|---|" + "---:|" * len(INVENTORIES))
    for d in designs:
        cells = []
        for inv in INVENTORIES:
            ratios = [idx[(inv, d, t)]["tokens_total"] / idx[(inv, "W1_nospace", t)]["tokens_total"] for t in tok_names]
            cells.append(_f(statistics.mean(ratios)))
        w(f"| {d} | " + " | ".join(cells) + " |")
    w("")

    # 6. 예시
    w("## 6. 예시 (어휘 추첨 0, 첫 메시지의 앞 3단어)")
    w("")
    for inv in ["naive", "token_picked"]:
        w(f"**{INV_LABEL[inv]}**")
        w("")
        w("| 표기 | o200k | cl100k | claude_legacy | mistral_sp |")
        w("|---|---|---|---|---|")
        for d in designs:
            ex = res["examples"][inv][d]
            cells = ["`" + "\\|".join(p.replace(" ", "␣") for p in ex["pieces"][t]) + "`"
                     for t in ["o200k", "cl100k", "claude_legacy", "mistral_sp"]]
            w(f"| {d} | " + " | ".join(cells) + " |")
        w("")
    w("(`␣` = 공백, `|` = 토큰 경계)")
    w("")
    w("## 7. 한계")
    w("")
    w("- 토큰 경계가 형태소와 맞는지만 쟀다. 어긋남이 LLM 의 읽기·쓰기 정확도를 실제로 떨어뜨리는지는 이 실험으로 알 수 없다 "
      "(`pilot_segmentation.py` 같은 모델 실험이 필요하다).")
    w("- 현행 Claude 토크나이저는 공개되지 않아 잴 수 없다. claude_legacy 는 Claude 2 시절 토크나이저로 대용 지표일 뿐이다.")
    w(f"- token-picked + W2 가 {len(ok)}개 토크나이저에서 통과한 것은 선정 기준(앞 공백 형태 1토큰)과 거의 같은 조건이라 예상된 결과다. "
      "이 실험이 새로 보여 주는 것은 (1) 문맥 안에서도 그 성질이 유지된다는 점, (2) 선정 때 자주 빠진 토크나이저"
      "(claude_legacy, mistral_sp)가 그대로 약점으로 남는다는 점이다.")
    w(f"- 어휘가 작다 (어근 {lex['roots']}개, 접사 {lex['affixes']}개, 가장 작은 풀에 맞춤). 추첨 간 범위를 2절 표에 적었다.")
    w(f"- 접사 단어 필터는 zipf < {AFFIX_MAX_ZIPF} 로 완화했다. W2 에서는 접사가 단독 토큰으로 보이므로 "
      "다른 언어의 짧은 단어처럼 보일 수 있다.")
    w("- token-picked 풀에는 vec, req, xor 처럼 영어 약어나 코드 조각으로 읽힐 수 있는 형태가 섞여 있다 (목록은 json 의 "
      "`token_picked_roots`). 단어 필터(wordfreq)가 이런 조각을 거르지 못하므로 사람 판독 저항성(G2)은 따로 따져야 한다.")
    w("- mistral_sp 의 붙여 쓴 형태 단독 토큰화는 toklib 으로 잴 수 없어 bare-picked 선정과 단독 측정에서 뺐다. "
      "메시지 전체 측정에는 포함했다.")
    w("")
    path.write_text("\n".join(L) + "\n")


def main() -> None:
    res, toks = run()
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "alignment.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    write_markdown(res, list(toks), OUT_DIR / "alignment.md")
    print(f"saved {OUT_DIR / 'alignment.json'} and alignment.md in {res['meta']['runtime_sec']}s")


if __name__ == "__main__":
    main()
