"""E2 boundary alignment: how well token boundaries match morpheme boundaries under each spelling scheme.

The same synthetic messages (300 messages of 20-40 morphemes) are written in several spelling schemes and with
several form lists (inventories). Each whole message is then tokenized with 7 tokenizers, and morpheme boundaries
are compared with token boundaries.

Inventories (roots CVC, affixes VC. 21 consonants, vowels aeiou)
- naive        : random forms that only pass the word filter
- token_picked : only forms whose leading-space form (" kat") is a single token in at least 6 of the 7 tokenizers
- bare_picked  : (auxiliary) only forms whose no-space form ("kat") is a single token in at least 5 of the 6 byte BPEs.
                 Added to see the best case when forms are chosen to suit glued writing (W1).

Word filter: max zipf < 3 across 11 languages (wordfreq). But only 1 VC affix form passes this cut, so
affixes use zipf < 4.5 (the results record the pool sizes under both cuts).

SentencePiece (mistral_sp) adds a dummy space (▁) to the start of the input by itself, so feeding " kat" gives two pieces, "▁" + "▁kat".
So the "leading-space form" for mistral_sp is measured by feeding "kat" (the same piece as "▁kat" inside a sentence).
For the same reason, the "no-space form" for mistral_sp cannot be measured separately with toklib, so it is left out of the bare_picked criterion.

Spelling schemes (example: kat-en mir-ob, 2 words)
- W1 nospace     : katenmirob      everything glued
- W2 spaced      : kat en mir ob   one space between morphemes
- W3 wordspaced  : katen mirob     one space between words
- W4 camel       : KatEnMirOb      no spaces, each morpheme capitalized
- W5 wordcamel   : KatEn MirOb     one space between words, each morpheme capitalized
- W6 lowercamel  : katEn mirOb     (added) one space between words; the first morpheme of a word is lowercase, the rest capitalized
- W7 rootcamel   : KatenMirob      (added) no spaces, only roots capitalized (can capitals replace spaces?)

Boundary rule: a space belongs to the following morpheme (" en"), because every tokenizer attaches a space to the following word.
So the position before the space is the morpheme boundary, and if the space becomes a token on its own, precision drops.

Metrics (tokenizer × spelling × inventory, computed over all messages pooled)
- tokens_per_morpheme : tokens / morphemes
- chars_per_token     : characters (including spaces) / tokens
- recall              : share of morpheme boundaries that are also token boundaries (both ends of the message excluded)
- precision           : share of token boundaries that are also morpheme boundaries (both ends of the message excluded)
- one_token_share     : share of morphemes that are exactly one token inside the message (leading space included)

Usage
    python3 alignment.py      # writes results/alignment.json and results/alignment.md
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
CONSONANTS = "bcdfghjklmnpqrstvwxyz"  # 21 letters (y included)
WORD_LANGS = ["en", "es", "de", "fr", "it", "pt", "nl", "tr", "id", "pl", "sv"]
ROOT_MAX_ZIPF = 3.0
AFFIX_MAX_ZIPF = 4.5  # at 3.0 only 1 VC affix remains
ZIPF_REPORT_THRESHOLDS = [3.0, 3.5, 4.0, 4.5, 5.0]
PICK_MIN = 6  # token_picked: out of 7
BARE_MIN = 5  # bare_picked: out of the 6 byte BPEs
SP_NAME = "mistral_sp"

N_MESSAGES = 300
MIN_MORPH, MAX_MORPH = 20, 40
N_DRAWS = 5  # how many times the lexicon (form assignment) is redrawn for each inventory
ZIPF_S = 1.0  # usage frequency of roots and affixes = rank^-s

# Message skeleton: predicate word + 1-3 argument words (+ modifier words)
PRED_AFFIX_P = [0.10, 0.25, 0.35, 0.20, 0.10]  # 0-4 affixes
ARG_AFFIX_P = [0.35, 0.50, 0.15]  # 0-2 affixes
MOD_AFFIX_P = [0.70, 0.30]  # 0-1 affixes
COMPOUND_P = {"pred": 0.10, "arg": 0.15, "mod": 0.0}  # probability of 2 roots (compound word)
N_ARGS_P = [0.30, 0.45, 0.25]  # 1-3 arguments
MOD_P = 0.30  # probability that a modifier word follows an argument

INVENTORIES = ["naive", "token_picked", "bare_picked"]
INV_LABEL = {"naive": "naive (random)", "token_picked": "token-picked (leading-space single token)",
             "bare_picked": "bare-picked (auxiliary, glued form single token)"}
DESIGNS = {
    "W1_nospace": "everything glued",
    "W2_spaced": "one space between morphemes",
    "W3_wordspaced": "one space between words, glued inside words",
    "W4_camel": "no spaces, each morpheme capitalized",
    "W5_wordcamel": "one space between words, each morpheme capitalized",
    "W6_lowercamel": "(added) one space between words; only the first morpheme of a word is lowercase, the rest capitalized",
    "W7_rootcamel": "(added) no spaces, only roots capitalized",
}
WORD_SPACED = {"W3_wordspaced", "W5_wordcamel", "W6_lowercamel"}

# Pass criteria: morpheme = token
STRICT = {"recall": 0.95, "precision": 0.95, "tpm": 1.05}
LOOSE = {"recall": 0.90, "precision": 0.90, "tpm": 1.10}

OUT_DIR = Path(__file__).resolve().parent / "results"


# ---------------------------------------------------------------- form pools

def max_zipf(form: str) -> float:
    return max(zipf_frequency(form, lang) for lang in WORD_LANGS)


def lead_space_single(tok, form: str) -> bool:
    """Is the form with a leading space (" kat") a single token inside a sentence?"""
    return tok.count(form if tok.name == SP_NAME else " " + form) == 1


def bare_single(tok, form: str) -> bool | None:
    """Is the form without a space ("kat") a single token? None for mistral_sp, which cannot be measured."""
    return None if tok.name == SP_NAME else tok.count(form) == 1


def build_pools(toks: dict) -> tuple[dict, dict]:
    """Build (root pool, affix pool) for each inventory, plus a table for reporting pool sizes."""
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
    # Count the forms that pass the word filter by the number of tokenizers (0-7) on which the leading-space form is a single token
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
    """Share of pool forms that are a single token when each is fed on its own (reference value without context)."""
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


# ---------------------------------------------------------------- message skeletons

def zipf_cum(n: int) -> list[float]:
    acc, out = 0.0, []
    for r in range(n):
        acc += 1.0 / (r + 1) ** ZIPF_S
        out.append(acc)
    return out


def make_word(rng: random.Random, kind: str, root_cum, affix_cum) -> list[tuple[str, int]]:
    """Word = 1-2 roots + 0-4 affixes. A morpheme is (kind 'R'/'A', rank)."""
    n_roots = 2 if rng.random() < COMPOUND_P[kind] else 1
    p = {"pred": PRED_AFFIX_P, "arg": ARG_AFFIX_P, "mod": MOD_AFFIX_P}[kind]
    n_aff = rng.choices(range(len(p)), weights=p)[0]
    roots = rng.choices(range(len(root_cum)), cum_weights=root_cum, k=n_roots)
    affixes: set[int] = set()
    while len(affixes) < n_aff:  # affixes do not repeat within a word
        affixes.add(rng.choices(range(len(affix_cum)), cum_weights=affix_cum)[0])
    # affixes go in a fixed slot order (by rank)
    return [("R", r) for r in roots] + [("A", a) for a in sorted(affixes)]


def make_sentence(rng: random.Random, root_cum, affix_cum) -> list[list[tuple[str, int]]]:
    words = [make_word(rng, "pred", root_cum, affix_cum)]
    for _ in range(rng.choices([1, 2, 3], weights=N_ARGS_P)[0]):
        words.append(make_word(rng, "arg", root_cum, affix_cum))
        if rng.random() < MOD_P:
            words.append(make_word(rng, "mod", root_cum, affix_cum))
    return words


def make_skeletons(rng: random.Random, n_roots: int, n_affixes: int) -> list[list[list[tuple[str, int]]]]:
    """N_MESSAGES message skeletons of MIN_MORPH to MAX_MORPH morphemes. Every inventory and spelling uses the same skeletons."""
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


# ---------------------------------------------------------------- spelling

def render(words: list[list[tuple[str, str]]], design: str) -> tuple[str, list[tuple[int, int, str, bool]]]:
    """List of words of (kind, form) -> (string, list of morpheme spans). Span = (start, end, kind, is first morpheme of its word).
    A leading space is included in the span of the following morpheme."""
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


# ---------------------------------------------------------------- measurement

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


# ---------------------------------------------------------------- run

def run() -> tuple[dict, dict]:
    t_start = time.time()
    toks = load_all()
    pools, pool_report = build_pools(toks)
    n_roots = min(len(p["roots"]) for p in pools.values())
    n_affixes = min(len(p["affixes"]) for p in pools.values())
    pool_report["lexicon_size_used"] = {"roots": n_roots, "affixes": n_affixes,
                                        "note": "every inventory uses a lexicon of the same size (matched to the smallest pool)"}
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

    # Tokens per message, W2 vs W1 (is the space free?)
    idx = {(r["inventory"], r["design"], r["tokenizer"]): r for r in rows}
    space_cost = {inv: {name: {
        "w2_tokens_per_message": round(idx[(inv, "W2_spaced", name)]["tokens_total"] / (N_MESSAGES * N_DRAWS), 2),
        "w1_tokens_per_message": round(idx[(inv, "W1_nospace", name)]["tokens_total"] / (N_MESSAGES * N_DRAWS), 2),
        "w2_lead_space_morpheme_one_token": idx[(inv, "W2_spaced", name)]["one_token_share_lead_space"],
        "w2_space_only_tokens_per_space": idx[(inv, "W2_spaced", name)]["space_only_tokens_per_space"],
    } for name in toks} for inv in INVENTORIES}

    # Examples (draw 0, first 3 words of the first message)
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


# ---------------------------------------------------------------- summary document

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
        """Min and max over draws of tokens/morpheme (mean over tokenizers)."""
        per = [statistics.mean(idx[(inv, d, t)]["tokens_per_morpheme_by_draw"][k] for t in tok_names)
               for k in range(N_DRAWS)]
        return min(per), max(per)

    def tpr(inv, d, t):
        r = idx[(inv, d, t)]
        return f"{_f(r['tokens_per_morpheme'])}, R {_f(r['recall'])}, P {_f(r['precision'])}"

    sc = res["space_cost_w2"]
    chars_w1 = idx[("naive", "W1_nospace", tok_names[0])]["chars_total"] / (N_MESSAGES * N_DRAWS)
    chars_w2 = idx[("naive", "W2_spaced", tok_names[0])]["chars_total"] / (N_MESSAGES * N_DRAWS)

    w("# E2 boundary alignment: agreement of morpheme and token boundaries by spelling scheme")
    w("")
    w("This summary was generated by `alignment.py`. Every number was measured by this script, and the raw data is in `alignment.json`.")
    w("")

    # 0. Summary (every number comes from computed values)
    w("## 0. Summary")
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
    w(f"1. **The combination closest to morpheme = token is `{b_d}` + {b_inv}.** It passed the strict criterion on {len(ok)}/{len(tok_names)} tokenizers"
      f" ({', '.join(ok)}), with tokens/morpheme {lo_ok if lo_ok == hi_ok else lo_ok + '–' + hi_ok}. "
      f"Tokenizers that did not pass: " + "; ".join(f"{t} ({tpr(b_inv, b_d, t)})" for t in bad) + ".")
    naive_txt = ("With the naive inventory, no tokenizer passed even the loose criterion under any spelling." if naive_max == 0 else
                 f"With the naive inventory, at most {naive_max} tokenizers passed the loose criterion under any spelling.")
    w(f"   - Combinations that passed on all 7: {'none' if not all7 else ', '.join(f'{d}+{inv}' for inv, d in all7)}. " + naive_txt)
    w("   - So spelling alone does not make morpheme = token. The forms must be chosen so that their leading-space form is a single token, "
      "and morphemes must be separated by spaces (W2) so that the chosen forms stay single tokens in context.")
    tp_free = [t for t in tok_names if sc["token_picked"][t]["w2_lead_space_morpheme_one_token"] >= 0.95]
    tp_diff = [sc["token_picked"][t]["w2_tokens_per_message"] - sc["token_picked"][t]["w1_tokens_per_message"]
               for t in tp_free]
    nv_share = [sc["naive"][t]["w2_lead_space_morpheme_one_token"] for t in tok_names]
    space_only_all = max(sc[inv][t]["w2_space_only_tokens_per_space"] for inv in INVENTORIES for t in tok_names)
    space_txt = ("No space-only token appeared in any tokenizer or inventory. " if space_only_all == 0 else
                 f"Space-only tokens appeared, up to {space_only_all:.3f} per space. ")
    w("2. **Spaces in W2**: " + space_txt +
      f"With token-picked forms, \" kat\" is a single token in context at least 95% of the time on "
      f"{len(tp_free)} tokenizers ({', '.join(tp_free)}), and on these W2 uses "
      f"{-max(tp_diff):.1f}–{-min(tp_diff):.1f} **fewer** tokens per message than W1. The space is more than free: it reduces tokens.")
    for t in [t for t in tok_names if t not in tp_free]:
        c = sc["token_picked"][t]
        w(f"   - {t}: single-token share {_pct(c['w2_lead_space_morpheme_one_token'])}, "
          f"W2 − W1 = {c['w2_tokens_per_message'] - c['w1_tokens_per_message']:+.1f} tokens/message → not free.")
    w(f"   - With naive forms the single-token share is {_pct(min(nv_share))}–{_pct(max(nv_share))}, so the space is not free.")
    w1 = {inv: (mean_over_toks(inv, "W1_nospace", "recall"), mean_over_toks(inv, "W1_nospace", "precision"),
                mean_over_toks(inv, "W1_nospace", "one_token_share"),
                mean_over_toks(inv, "W1_nospace", "one_token_share_root"),
                mean_over_toks(inv, "W1_nospace", "one_token_share_affix")) for inv in INVENTORIES}
    w("3. **Cost of glued writing (W1)**: depending on the inventory, W1 uses more or fewer tokens than W2, "
      "but the boundary mismatch is similarly large in every inventory. (Mean over tokenizers)")
    for inv in INVENTORIES:
        rr, pp, one, one_r, one_a = w1[inv]
        others = {d: tok_per_msg(inv, d) for d in designs}
        cheapest = min(others, key=others.get)
        rel = 100 * (others["W1_nospace"] / others["W2_spaced"] - 1)
        w(f"   - {inv}: recall {_f(rr)}, precision {_f(pp)}, single-token morphemes {_pct(one)} (roots {_pct(one_r)}, affixes {_pct(one_a)}). "
          f"Tokens per message W1 {others['W1_nospace']:.1f} / W2 {others['W2_spaced']:.1f} (W1 is {rel:+.0f}% vs W2), "
          f"cheapest spelling {cheapest} ({others[cheapest]:.1f}).")
    w("   - In glued writing, BPE splits off the first consonant of a root (`mab`+`ef` → `m|ab|ef`) or groups the last consonant "
      "of a root with the following affix (`mul`+`ox` → `mu|lox`, claude_legacy). So roots in particular are often split. Even when forms "
      f"are chosen by their glued form (bare-picked), recall stays at {_f(w1['bare_picked'][0])}.")
    w(f"   - Character counts are W1 {chars_w1:.1f} and W2 {chars_w2:.1f} characters/message, so spaces add {100 * (chars_w2 / chars_w1 - 1):.0f}% "
      "characters, but this is separate from the token count.")
    cam = [idx[(inv, d, t)] for inv in INVENTORIES for d in ("W4_camel", "W5_wordcamel") for t in tok_names]
    w(f"4. **Capitalized spellings (W4, W5)**: capitals create token boundaries, so recall is high at {_f(min(r['recall'] for r in cam))}–"
      f"{_f(max(r['recall'] for r in cam))}, but forms that start with a capital are often not a single token"
      f" (`G|id`), so tokens/morpheme is {_f(min(r['tokens_per_morpheme'] for r in cam))}–{_f(max(r['tokens_per_morpheme'] for r in cam))} "
      f"and precision {_f(min(r['precision'] for r in cam))}–{_f(max(r['precision'] for r in cam))}. "
      "The added W6 (lowercamel, token-picked) passed only the loose criterion, on "
      + ", ".join(f"{t} ({tpr('token_picked', 'W6_lowercamel', t)})" for t in tok_names
                  if idx[("token_picked", "W6_lowercamel", t)]["pass_loose"])
      + ".")
    ps = pools["pool_sizes"]["token_picked"]
    hist = pools["word_filtered_forms_by_n_lead_space_single"]
    w(f"5. **The form pool is the bottleneck.** Among CVC forms that pass the word filter (zipf < {ROOT_MAX_ZIPF}), there are {ps['roots']} token-picked roots"
      f" ({hist['roots_cvc'][7]} of them are single tokens on all 7), far short of the documented target of 500–1,000 roots. "
      f"Relaxing the filter to zipf < 4.0 gives {pools['pool_sizes_by_zipf_threshold']['token_picked']['4.0']['roots_cvc']}. "
      "Only 1 VC affix form passes zipf < 3, so the affix filter was relaxed.")
    w("")
    w("## 1. Setup")
    w("")
    w(f"- {st['messages']} synthetic messages of {st['morphemes_per_message']['min']}–{st['morphemes_per_message']['max']} morphemes "
      f"(mean {st['morphemes_per_message']['mean']}), {st['words_per_message_mean']} words on average, "
      f"affix share {_pct(st['affix_share'])}, compound word (2 roots) share {_pct(st['compound_word_share'])}.")
    w("- A message is a sequence of sentences (predicate word + 1–3 argument words + an occasional modifier word). Root and affix usage frequency is rank^-1 (Zipf).")
    w(f"- All inventories and spellings use **the same skeletons**; only the forms change. For each inventory the lexicon (form assignment) was drawn {meta['n_draws']} times and the results pooled.")
    lex = pools["lexicon_size_used"]
    w(f"- Lexicon size: {lex['roots']} roots, {lex['affixes']} affixes (shared by the three inventories, matched to the smallest pool).")
    w("- Boundary rule: a space belongs to the following morpheme. If a space becomes a separate token, precision drops.")
    w("- The \"leading-space form\" for mistral_sp is measured by feeding `kat` (SentencePiece adds `▁` by itself, so this is the same as `▁kat`).")
    w("")
    w("### Form pool sizes")
    w("")
    w("| Inventory | Roots CVC | Affixes VC | Selection criterion |")
    w("|---|---:|---:|---|")
    crit = {"naive": "word filter only",
            "token_picked": f"leading-space form is a single token on at least {PICK_MIN} of 7",
            "bare_picked": f"glued form is a single token on at least {BARE_MIN} of the 6 byte BPEs (mistral_sp excluded)"}
    for inv in INVENTORIES:
        ps = pools["pool_sizes"][inv]
        w(f"| {INV_LABEL[inv]} | {ps['roots']} | {ps['affixes']} | {crit[inv]} |")
    w("")
    w(f"Candidates: {pools['candidates']['cvc']} CVC, {pools['candidates']['vc']} VC. "
      f"Word filter = max zipf across 11 languages < {ROOT_MAX_ZIPF} (roots), < {AFFIX_MAX_ZIPF} (affixes).")
    w("")
    w("**Why the affix filter was relaxed**: applying zipf < 3 to VC as is leaves almost no affixes. Pool sizes by threshold (roots / affixes):")
    w("")
    ths = [str(t) for t in ZIPF_REPORT_THRESHOLDS]
    w("| Inventory | " + " | ".join(f"zipf < {t}" for t in ths) + " |")
    w("|---|" + "---:|" * len(ths))
    for inv in INVENTORIES:
        bt = pools["pool_sizes_by_zipf_threshold"][inv]
        w(f"| {inv} | " + " | ".join(f"{bt[t]['roots_cvc']} / {bt[t]['affixes_vc']}" for t in ths) + " |")
    w("")
    w("Under the strict filter (zipf < 3) there are only "
      f"{pools['pool_sizes']['token_picked']['roots']} token-picked roots. That is far short of the documented target of 500–1,000 roots.")
    w("")

    # 2. Main answer
    w("## 2. Main result: the spelling that achieves morpheme = token on the most tokenizers")
    w("")
    w(f"Pass criteria (strict): recall ≥ {STRICT['recall']}, precision ≥ {STRICT['precision']}, tokens/morpheme ≤ {STRICT['tpm']}. "
      f"Loose: {LOOSE['recall']} / {LOOSE['precision']} / {LOOSE['tpm']}. Cell = number of tokenizers that pass (strict / loose, out of 7).")
    w("")
    w("| Spelling | " + " | ".join(INVENTORIES) + " |")
    w("|---|" + "---:|" * len(INVENTORIES))
    for d in designs:
        w(f"| {d} | " + " | ".join(f"{n_pass(inv, d, 'strict')} / {n_pass(inv, d, 'loose')}" for inv in INVENTORIES) + " |")
    w("")
    w("### Mean over tokenizers (simple mean of 7)")
    w("")
    for inv in INVENTORIES:
        w(f"**{INV_LABEL[inv]}**")
        w("")
        w("| Spelling | Tokens/morpheme | Range across draws | Chars/token | recall | precision | Single-token morphemes | Chars per message | Tokens per message |")
        w("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for d in designs:
            chars = idx[(inv, d, tok_names[0])]["chars_total"] / (N_MESSAGES * N_DRAWS)
            toks_msg = statistics.mean(idx[(inv, d, t)]["tokens_total"] for t in tok_names) / (N_MESSAGES * N_DRAWS)
            lo, hi = draw_range(inv, d)
            w(f"| {d} | {_f(mean_over_toks(inv, d, 'tokens_per_morpheme'))} | {_f(lo)}–{_f(hi)} | {_f(mean_over_toks(inv, d, 'chars_per_token'))} | "
              f"{_f(mean_over_toks(inv, d, 'recall'))} | {_f(mean_over_toks(inv, d, 'precision'))} | "
              f"{_pct(mean_over_toks(inv, d, 'one_token_share'))} | {chars:.1f} | {toks_msg:.1f} |")
        w("")

    # 3. Per-tokenizer tables
    w("## 3. Results by tokenizer")
    w("")
    header = "| Spelling | " + " | ".join(tok_names) + " |"
    sep = "|---|" + "---:|" * len(tok_names)
    for inv in INVENTORIES:
        w(f"### {INV_LABEL[inv]}")
        w("")
        w("Tokens/morpheme (the min–max across the 5 lexicon draws is in `tokens_per_morpheme_by_draw` in the json)")
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
        w("Share of morphemes that are exactly one token")
        w("")
        w(header)
        w(sep)
        for d in designs:
            w(f"| {d} | " + " | ".join(_pct(idx[(inv, d, t)]["one_token_share"]) for t in tok_names) + " |")
        w("")

    # 4. Is the space free?
    w("## 4. Is the space in W2 free?")
    w("")
    w("Cell = share of morphemes with a leading space (\" kat\") that are exactly one token in context / space-only tokens (per space) / "
      "tokens per message W2 − W1 / verdict. The verdict is \"free\" if the single-token share is at least 95% and there are no space tokens.")
    w("")
    w("| Tokenizer | " + " | ".join(INVENTORIES) + " |")
    w("|---|" + "---|" * len(INVENTORIES))
    for t in tok_names:
        cells = []
        for inv in INVENTORIES:
            c = sc[inv][t]
            diff = c["w2_tokens_per_message"] - c["w1_tokens_per_message"]
            free = c["w2_lead_space_morpheme_one_token"] >= 0.95 and c["w2_space_only_tokens_per_space"] == 0
            cells.append(f"{_pct(c['w2_lead_space_morpheme_one_token'])} / {_f(c['w2_space_only_tokens_per_space'], 3)} / "
                         f"{diff:+.1f} / {'free' if free else 'not free'}")
        w(f"| {t} | " + " | ".join(cells) + " |")
    w("")
    w("Single-token share measured one form at a time without context (whole pool; leading-space lowercase / leading-space capitalized / glued lowercase / glued capitalized):")
    w("")
    w("| Tokenizer | " + " | ".join(INVENTORIES) + " |")
    w("|---|" + "---|" * len(INVENTORIES))
    iso = pools["isolated_single_token_rates"]
    for t in tok_names:
        w(f"| {t} | " + " | ".join(
            f"{_pct(iso[inv][t]['lead_space'])} / {_pct(iso[inv][t]['lead_space_cap'])} / "
            f"{_pct(iso[inv][t]['bare'])} / {_pct(iso[inv][t]['bare_cap'])}" for inv in INVENTORIES) + " |")
    w("")
    w("The glued form cannot be measured separately for mistral_sp with toklib, so it is shown as `-`.")
    w("")

    # 5. Cost of glued writing
    w("## 5. Actual cost of glued writing (W1)")
    w("")
    w("Recall by boundary type (mean over tokenizers): word boundaries / morpheme boundaries inside words.")
    w("")
    w("| Spelling | " + " | ".join(INVENTORIES) + " |")
    w("|---|" + "---|" * len(INVENTORIES))
    for d in designs:
        w(f"| {d} | " + " | ".join(
            f"{_f(mean_over_toks(inv, d, 'recall_word_boundary'))} / {_f(mean_over_toks(inv, d, 'recall_inner_boundary'))}"
            for inv in INVENTORIES) + " |")
    w("")
    w("Share of morphemes that are exactly one token (mean over tokenizers): roots / affixes.")
    w("")
    w("| Spelling | " + " | ".join(INVENTORIES) + " |")
    w("|---|" + "---|" * len(INVENTORIES))
    for d in designs:
        w(f"| {d} | " + " | ".join(
            f"{_pct(mean_over_toks(inv, d, 'one_token_share_root'))} / {_pct(mean_over_toks(inv, d, 'one_token_share_affix'))}"
            for inv in INVENTORIES) + " |")
    w("")
    w("Tokens per message relative to W1 (mean over tokenizers; below 1 means fewer than W1):")
    w("")
    w("| Spelling | " + " | ".join(INVENTORIES) + " |")
    w("|---|" + "---:|" * len(INVENTORIES))
    for d in designs:
        cells = []
        for inv in INVENTORIES:
            ratios = [idx[(inv, d, t)]["tokens_total"] / idx[(inv, "W1_nospace", t)]["tokens_total"] for t in tok_names]
            cells.append(_f(statistics.mean(ratios)))
        w(f"| {d} | " + " | ".join(cells) + " |")
    w("")

    # 6. Examples
    w("## 6. Examples (lexicon draw 0, first 3 words of the first message)")
    w("")
    for inv in ["naive", "token_picked"]:
        w(f"**{INV_LABEL[inv]}**")
        w("")
        w("| Spelling | o200k | cl100k | claude_legacy | mistral_sp |")
        w("|---|---|---|---|---|")
        for d in designs:
            ex = res["examples"][inv][d]
            cells = ["`" + "\\|".join(p.replace(" ", "␣") for p in ex["pieces"][t]) + "`"
                     for t in ["o200k", "cl100k", "claude_legacy", "mistral_sp"]]
            w(f"| {d} | " + " | ".join(cells) + " |")
        w("")
    w("(`␣` = space, `|` = token boundary)")
    w("")
    w("## 7. Limitations")
    w("")
    w("- This experiment only measured whether token boundaries match morphemes. It cannot tell whether a mismatch actually lowers "
      "an LLM's reading and writing accuracy (that needs a model experiment such as `pilot_segmentation.py`).")
    w("- The current Claude tokenizer is not public, so it cannot be measured. claude_legacy is the Claude 2-era tokenizer and only a proxy.")
    w(f"- token-picked + W2 passing on {len(ok)} tokenizers is an expected result, because the condition is almost the same as the selection criterion (leading-space form is a single token). "
      "What this experiment adds is (1) that the property holds in context too, and (2) that the tokenizers often left out during selection "
      "(claude_legacy, mistral_sp) remain weak points.")
    w(f"- The lexicon is small ({lex['roots']} roots, {lex['affixes']} affixes, matched to the smallest pool). The range across draws is given in the section 2 tables.")
    w(f"- The word filter for affixes was relaxed to zipf < {AFFIX_MAX_ZIPF}. In W2, affixes appear as standalone tokens, "
      "so they may look like short words of other languages.")
    w("- The token-picked pool contains forms such as vec, req and xor that can be read as English abbreviations or code fragments (the list is "
      "`token_picked_roots` in the json). The word filter (wordfreq) does not catch such fragments, so resistance to human reading (G2) must be assessed separately.")
    w("- Standalone tokenization of glued forms cannot be measured for mistral_sp with toklib, so mistral_sp was left out of the bare-picked selection and the standalone measurements. "
      "It is included in the whole-message measurements.")
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
