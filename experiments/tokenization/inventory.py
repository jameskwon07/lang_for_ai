"""Experiment E1: survey of the morpheme candidate inventory.

For each shape (letter pattern: CVC, VC, ...) and each spelling (lowercase, leading space, capitalized first letter),
count how many candidate forms are a single token on the 7 tokenizers.
Forms that match real words in several languages bring their original meaning into an LLM (semantic interference),
so they are filtered by word frequency.

Usage (from this directory)
    python3 inventory.py      # writes results/inventory.json and results/inventory.md (about 1 minute with 4 processes)

Method
- Each form is appended to a context and tokenized; only the tokens after the end of the context are counted.
  If a context token and the form merge into one token (no boundary), the form counts as not a single token.
    leading-space spelling (" kat", " Kat") : context "the"  → "the kat"   a form that follows a space mid-sentence
    glued spelling         ("kat", "Kat")   : context "1"    → "1kat"      a form that starts without a space (for glued text)
- Why a context is needed: SentencePiece (mistral_sp) adds a dummy space (▁) at the start of the input, so
  tokenizing "kat" alone actually measures "▁kat" (= the leading-space spelling), and tokenizing " kat" alone measures "▁▁kat".
  The other tokenizers' pre-tokenization regexes already split digits from letters and words from spaces, so
  the result is the same even with the context. The sanity section checks this.
- The single-token value for the glued spelling is the value "when the form comes at the start of a run of letters".
  Inside a continuous string of letters (katenmirob), a form can be cut together with neighboring letters; another experiment (E2) covers that.
- Real-word filter: measure wordfreq zipf_frequency in 11 languages and use the maximum (lowercase).
  zipf 3.0 is roughly once per million words; 2.0 is once per ten million words.
  Frequencies are measured only for forms that affect the results (a single token in any spelling, or 2 tokens or fewer on all 7)
  and for every form of shapes with 11,025 forms or fewer (to save time).

No randomness is used, so results are the same on every run.
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

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")  # silence the HF tokenizers warning after fork

from wordfreq import get_frequency_dict, zipf_frequency  # noqa: E402

from toklib import load_all  # noqa: E402

SEED = 20261007  # no randomness is used; kept to follow the repository convention
VOWELS = "aeiou"
CONSONANTS = "".join(c for c in string.ascii_lowercase if c not in VOWELS)  # 21 letters, including y
WORD_LANGS = ["en", "es", "de", "fr", "it", "pt", "nl", "tr", "id", "pl", "sv"]
FILTERS = ["none", "lt3", "lt2"]  # no filter, max zipf < 3.0, < 2.0
FILTER_CUT = {"none": math.inf, "lt3": 3.0, "lt2": 2.0}
SWEEP = [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, math.inf]  # count at each zipf threshold (inf = no filter)
FULL_ZIPF_MAX_FORMS = 11025  # for shapes with at most this many forms, measure the frequency of every form
WORKERS = min(4, os.cpu_count() or 1)  # number of measuring processes (does not affect the results)

# Consonant-initial shapes = root candidates, vowel-initial shapes = grammatical morpheme candidates.
# Glued text is split by the rule 'if the next letter is a consonant, a root starts; if it is a vowel, a grammatical form starts',
# so each role uses one shape.
ROOT_SHAPES = ["CV", "CVV", "CCV", "CVC", "CVCV", "CCVC", "CVCC", "CVCVC"]
GRAM_SHAPES = ["V", "VV", "VC", "VCV", "VCC", "VCVC"]
SHAPES = sorted(ROOT_SHAPES + GRAM_SHAPES, key=lambda s: (len(s), s))

# spelling name → (context, form → spelled string)
VARIANTS = {
    "bare": ("1", lambda f: f),
    "space": ("the", lambda f: " " + f),
    "cap": ("1", lambda f: f.capitalize()),
    "space_cap": ("the", lambda f: " " + f.capitalize()),
}
VARIANT_LABEL = {"bare": "kat", "space": "␣kat", "cap": "Kat", "space_cap": "␣Kat"}

# agreement levels across tokenizers
LEVELS = ["all7", "no_sp", "ge6", "ge5", "claude", "le2_all7"]
LEVEL_LABEL = {
    "all7": "all 7",
    "no_sp": "all 6 except mistral_sp",
    "ge6": "6 or more of 7",
    "ge5": "5 or more of 7",
    "claude": "claude_legacy alone",
    "le2_all7": "2 tokens or fewer on all 7",
}
MAIN_LEVELS = ["all7", "no_sp", "ge6", "claude"]
TARGET_ROOTS, TARGET_GRAM = 1000, 100

OUT_DIR = Path(__file__).resolve().parent / "results"
NAMES: list[str] = []  # filled in tokenizer order by main()


# ---------------------------------------------------------------- measurement

def expand(shape: str) -> list[str]:
    pools = [VOWELS if ch == "V" else CONSONANTS for ch in shape]
    return ["".join(p) for p in itertools.product(*pools)]


def span_count(tok, ctx: str, s: str) -> int:
    """Number of tokens that s takes when appended after the context ctx. -1 if it merges with the context into one token."""
    cut, pos, n = len(ctx), 0, 0
    for p in tok.pieces(ctx + s):
        start, pos = pos, pos + len(p)
        if start < cut < pos:
            return -1
        if start >= cut and p:
            n += 1
    return n


def word_freq(form: str) -> dict:
    """Maximum zipf over the 11 languages, that language, and the English zipf."""
    zs = [(zipf_frequency(form, lang), lang) for lang in WORD_LANGS]
    z, lang = max(zs, key=lambda x: x[0])
    return {"max": z, "lang": lang if z > 0 else None, "en": zs[0][0]}


def level_ok(c: tuple[int, ...], level: str) -> bool:
    """c = tuple of token counts per tokenizer (NAMES order, -1 = merged with the context)."""
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
    """Does this form enter any count? (a single token on at least one tokenizer, or 2 tokens or fewer on all 7)"""
    return any(x == 1 for x in c) or level_ok(c, "le2_all7")


_TOKS: dict = {}  # tokenizers that the worker processes inherit through fork


def _measure_chunk(args: tuple[str, list[str]]) -> tuple[dict, dict]:
    """Measure one chunk of forms. Runs in a worker process."""
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
    """counts[shape][variant][form] = tuple of token counts per tokenizer, zipf[form] = word_freq(form).

    Splits the forms into chunks and measures them in several (forked) processes. Chunks are merged in order,
    so the results do not depend on the number of processes.
    """
    _TOKS.update(toks)
    word_freq("kat")  # load the frequency lists first so that the worker processes inherit them
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
    """(1) Disagreements in the single-token verdict between the in-context value and standalone tokenization
    (toklib is_single_token), over all of CVC and VC.
    (2) Number of forms, over all shapes, that merged with the context."""
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


# ---------------------------------------------------------------- aggregation

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
                # number of forms that pass the word filter regardless of tokenization (only shapes where every form's frequency was measured)
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
    """Share of real words (max zipf ≥ 3.0) by the number of tokenizers (k) on which the form is a single token.
    Only shapes where every form's frequency was measured."""
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
    """Set of proper prefixes and set of proper substrings of the words with zipf ≥ 3.0 in the 11 languages.

    Uses the same wordfreq list (best) as zipf_frequency. zipf ≥ 3.0 ⇔ frequency ≥ 1e-6.
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
    """Share of forms that pass the word filter (zipf < 3.0) and are fragments of common words.

    ␣ spelling: is it a proper prefix of a common word (zipf ≥ 3.0)? (e.g. ' calc' ← calculate)
    Glued spelling: is it a proper substring somewhere inside a common word? (e.g. 'ated' ← created)
    Compares forms that are single tokens on all 7 with forms that are a single token on no tokenizer (baseline).
    The baseline is given only for shapes where every form's frequency was measured.
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
    """Per-form detail: includes only forms that are a single token on at least one tokenizer in some spelling."""
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
    """Productivity by letter. For each shape, spelling and position, the single-token share of the forms that contain the letter."""
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
    """Greedy search that removes consonants from CVC roots one at a time.

    Target = CVC forms that are single tokens at the given agreement level (no word filter; tokenization only).
    Remove first the consonant whose removal loses the fewest target forms. On a tie, the consonant that comes first
    alphabetically.
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
    """Pick the n candidates with the lowest token cost from the candidate pool (word filter applied).

    Rank: number of tokenizers on which the form is not a single token → total tokens over the 7 → max tokens → alphabetical.
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
    """Key question: is there a shape and spelling combination that supplies 1,000 roots + 100 grammatical forms?"""
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


# ---------------------------------------------------------------- report

def pct(x: float) -> str:
    return f"{100 * x:.0f}"


def md_table(header: list[str], rows: list[list], align: str | None = None) -> list[str]:
    align = align or ("l" + "r" * (len(header) - 1))
    sep = ["---:" if a == "r" else "---" for a in align]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(sep) + " |"]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return lines


COMBO_LABEL = {
    "glued": "Glued (no spaces)",
    "glued_camel": "Glued + capitalized first letter of each morpheme",
    "spaced": "One space between morphemes",
    "wordspaced": "Space before roots only (grammatical forms glued)",
    "wordspaced_cap": "Space before roots + capital letter (grammatical forms glued)",
}


def _examples(lists: dict, cands: list[tuple[str, str, str]]) -> str:
    """Cite an example form only if it is actually in the list of forms single on all 7 & zipf < 3.0."""
    ok = [f"`{form}`" for shape, var, form in cands
          if form.strip() in {f for f, _ in lists[shape][var]["all7_lt3"]}]
    return f" (e.g. {', '.join(ok)})" if ok else ""


def key_answer(stats: dict, des: dict, mech: dict, frag: dict, lists: dict) -> list[str]:
    """Build the sentences of the key answer from the measured values."""
    L: list[str] = []
    best = des["best_single_shape"]
    pools = des["pools_variable_length"]
    V = VARIANT_LABEL

    def top(role: str, lv: str, flt: str, variants=VARIANTS) -> tuple[int, str, str]:
        return max(((best[role][v][lv][flt]["count"], best[role][v][lv][flt]["shape"], v) for v in variants),
                   key=lambda x: (x[0], x[2] == "space", x[1]))

    # 1. verdict
    met = [(c, lv, flt) for c, d in des["combos"].items() for lv in ["all7", "no_sp", "ge6"] for flt in ["lt3", "lt2"]
           if d["levels"][lv][flt]["meets"]]
    if met:
        L.append("- **Combinations that meet the target**: " + ", ".join(f"{COMBO_LABEL[c]} ({LEVEL_LABEL[lv]}, {flt})" for c, lv, flt in met))
    else:
        L.append(f"- **No shape and spelling combination meets the target ({TARGET_ROOTS:,} roots + {TARGET_GRAM} grammatical forms, "
                 "single token, word filter zipf < 3.0).** "
                 "None does at any level: all 7, the 6 other than mistral_sp, or 6 or more of 7. The roots are what falls short.")
    # 2. grammatical forms only
    g_ok = [(sh, v, flt, stats[sh][v]["agreement"]["all7"][flt]) for flt in ["lt3", "lt2"] for v in VARIANTS for sh in GRAM_SHAPES
            if stats[sh][v]["agreement"]["all7"][flt] >= TARGET_GRAM]
    if g_ok:
        L.append(f"- {TARGET_GRAM} grammatical forms can be filled with forms that are single tokens on all 7: "
                 + ", ".join(f"{sh} {V[v]} {n:,} (zipf < {FILTER_CUT[flt]:.1f})" for sh, v, flt, n in g_ok)
                 + ". All of these are glued spellings, so they fit the glued design or the 'space before roots only' design. "
                 "But almost all of these forms are fragments inside common words" + _examples(lists, [("VCVC", "bare", "ated"), ("VCVC", "bare", "atic"),
                                                                     ("VCC", "bare", "ity")]) + " (section 2.5).")
    # 2-1. earlier sketch (docs/01: CVC roots + VC affixes, glued)
    cb, vb = stats["CVC"]["bare"]["agreement"]["all7"], stats["VC"]["bare"]["agreement"]["all7"]
    L.append(f"- Measuring the docs/01 sketch (glued CVC roots + VC affixes) as is: CVC kat single on all 7: {cb['none']:,} → zipf < 3.0: {cb['lt3']:,} → < 2.0: {cb['lt2']:,}; "
             f"VC kat single on all 7: {vb['none']:,} → zipf < 3.0: {vb['lt3']:,} → < 2.0: {vb['lt2']:,}. "
             f"Regardless of tokenization, only {stats['VC']['bare']['n_pass_filter']['lt3']:,} of the 105 VC forms has zipf < 3.0 (almost every two-letter string is a word or abbreviation in some language).")
    # 3. maximums
    for lv in ["all7", "no_sp"]:
        r = [top("root", lv, f) for f in FILTERS]
        L.append(f"- Maximum roots ({LEVEL_LABEL[lv]}, one shape): no filter: {r[0][0]:,} ({r[0][1]} {V[r[0][2]]}) → "
                 f"zipf < 3.0: {r[1][0]:,} ({r[1][1]} {V[r[1][2]]}) → zipf < 2.0: {r[2][0]:,} ({r[2][1]} {V[r[2][2]]}).")
    p = pools["space"]
    L.append(f"- Root pool that combines all consonant-initial shapes in a spaced design (␣kat, single token on all 7): no filter: {p['root']['all7']['none']:,} → "
             f"zipf < 3.0: {p['root']['all7']['lt3']:,} → < 2.0: {p['root']['all7']['lt2']:,}. "
             f"Without the word filter it exceeds 1,000; with the filter it falls far short.")
    # 4. cause
    parts = []
    for var in ["space", "bare"]:
        m = mech["CVC"][var]
        hi, lo = m.get(str(len(NAMES))), m.get("0")
        if hi and lo:
            parts.append(f"CVC {V[var]}: {pct(hi['word_ge3_share'])}% of the {hi['n']:,} forms that are single tokens on all 7, "
                         f"{pct(lo['word_ge3_share'])}% of the {lo['n']:,} forms that are a single token on no tokenizer")
    L.append("- The bottleneck is the word filter. Share of forms with zipf ≥ 3.0 in some language — " + "; ".join(parts) + ". "
             "A letter string that a tokenizer made into one token is a string that occurs often in the first place, "
             "so forms that are single tokens on more tokenizers are more often real words (section 2.4).")
    npf = stats["CVC"]["bare"]["n_pass_filter"]
    L.append(f"- Regardless of tokenization, only {npf['lt3']:,} of the 2,205 CVC forms have zipf < 3.0, and only {npf['lt2']:,} have zipf < 2.0. "
             f"CVC alone cannot supply 1,000 roots even before token counts are considered.")
    # 5. fragments
    fs = frag["shapes"]
    items = []
    for shape, var in [("CVCC", "space"), ("CVCVC", "space"), ("VCVC", "bare"), ("CVC", "space")]:
        d = fs[shape][var]
        if d["all7"]["n"]:
            base = d.get("none_single")
            items.append(f"{shape} {V[var]} {pct(d['all7']['fragment_share'])}% (of {d['all7']['n']:,})"
                         + (f", baseline (not a single token) {pct(base['fragment_share'])}%" if base and base["n"] else ""))
    non_frag = sorted({f for d in fs.values() for var in ["bare", "space"] for f in d[var]["all7"]["non_fragment_examples"]})
    L.append("- Even the single tokens that pass the filter are mostly fragments of common words"
             + _examples(lists, [("CVCC", "space", " calc"), ("CVCVC", "space", " gover"), ("VCVC", "bare", "ated")]) + ". "
             "Share of forms that are a proper prefix (␣ spelling) or a proper substring (glued spelling) of a common word: " + "; ".join(items) + " (section 2.5). "
             "The only forms single on all 7 that are not fragments: " + (", ".join(f"`{f}`" for f in non_frag) or "none") + " (many are code identifiers). "
             "The zipf filter removes only 'the word itself'; it does not remove the meaning that such fragments bring in.")
    # 6. compromises
    bn = des["best_n"]
    t = []
    for var, key in [("space", "root:pool:lt3"), ("space", "root:CVCV:lt3"), ("bare", "root:CVCC:lt3")]:
        d = bn[var][key]
        if d.get("picked"):
            sh = key.split(":")[1]
            t.append(f"{'root pool (spaced designs only)' if sh == 'pool' else sh} {V[var]}: {d['all7_single']:,} single on all 7, {d['le2_all7']:,} at 2 tokens or fewer on all 7, "
                     f"mean tokens o200k {d['mean_tokens']['o200k']:.2f} / claude_legacy {d['mean_tokens']['claude_legacy']:.2f} / "
                     f"mistral_sp {d['mean_tokens']['mistral_sp']:.2f}")
    L.append(f"- Compromise 1 (allow 2 tokens): picking the {TARGET_ROOTS:,} roots with the lowest token cost while keeping zipf < 3.0 — " + "; ".join(t) + " (section 2.3).")
    sw = stats["CVC"]["space"]["zipf_sweep"]
    j3, j4 = SWEEP.index(3.0), SWEEP.index(4.0)
    L.append(f"- Compromise 2 (relax the filter): CVC ␣kat forms that are single tokens on all 7: {sw['max11']['all7'][j3]:,} at zipf < 3.0 and "
             f"{sw['max11']['all7'][j4]:,} at < 4.0 by the 11-language measure; by English alone, {sw['en']['all7'][j3]:,} at < 3.0 and {sw['en']['all7'][j4]:,} at < 4.0 (section 2.1). "
             "Relaxing the filter means using real words as roots.")
    ex = stats["CVC"]["space"]["all7_excluded_by_lt3"]
    langs = ", ".join(f"{k} {v}" for k, v in list(ex["by_lang"].items())[:6])
    L.append(f"- Of the CVC ␣kat forms that are single tokens on all 7, those removed for zipf ≥ 3.0, split by the language with the highest frequency: {langs} …; "
             f"of these, {ex['en_below_3']:,} have an English zipf below 3.0.")
    # 7. claude
    c_rn, c_r, c_g = top("root", "claude", "none"), top("root", "claude", "lt3"), top("gram", "claude", "lt3")
    pc = pools["space"]["root"]["per_tokenizer"]["claude_legacy"]
    worse = [n for n in NAMES if stats["CVC"]["space"]["per_tokenizer"][n]["none"] < stats["CVC"]["bare"]["per_tokenizer"][n]["none"]]
    L.append(f"- claude_legacy alone: roots (one shape) max {c_rn[0]:,} with no filter ({c_rn[1]} {V[c_rn[2]]}), max {c_r[0]:,} at zipf < 3.0 "
             f"({c_r[1]} {V[c_r[2]]}); ␣kat root pool at zipf < 3.0: {pc['lt3']:,}; grammatical forms max {c_g[0]:,} at zipf < 3.0 ({c_g[1]} {V[c_g[2]]}). "
             f"Tokenizers with fewer CVC single tokens for ␣kat than for kat: {', '.join(worse) or 'none'} "
             f"(claude_legacy ␣kat {stats['CVC']['space']['per_tokenizer']['claude_legacy']['none']:,} / kat {stats['CVC']['bare']['per_tokenizer']['claude_legacy']['none']:,}). "
             "On the other tokenizers, CVC has at least as many single tokens for ␣kat as for kat.")
    return L


def write_md(path: Path, stats: dict, lists: dict, letters: dict, reduced: dict, des: dict, mech: dict,
             frag: dict, sanity_res: dict) -> None:
    L: list[str] = []
    a = L.append
    a("# E1. Morpheme candidate inventory: how many forms fit in one token?")
    a("")
    a("Output of `python3 inventory.py`. All numbers and form lists are in [inventory.json](inventory.json). "
      "Spellings are written `kat` (glued, lowercase), `␣kat` (leading space), `Kat` (glued, capitalized), `␣Kat` (leading space + capitalized). "
      "'zipf < 3.0' means that the highest zipf frequency across the 11 languages (" + ", ".join(WORD_LANGS) + ") is below 3.0.")
    a("")

    # ---- 1. key answer
    a("## 1. Answer to the key question")
    a("")
    a(f"Question: is there a shape and spelling that can supply about {TARGET_ROOTS:,} roots and about {TARGET_GRAM} grammatical forms "
      "with forms that are a single token on all 7 tokenizers (or on all but mistral_sp) and are not common words?")
    a("")
    L.extend(key_answer(stats, des, mech, frag, lists))
    a("")
    a("### 1.1 Maximum per design (one shape each)")
    a("")
    a("For roots, pick the one consonant-initial shape (" + ", ".join(ROOT_SHAPES) + ") that yields the most forms; for grammatical forms, "
      "the one vowel-initial shape (" + ", ".join(GRAM_SHAPES) + ") that yields the most. "
      "This is the condition under which even glued text can be split by the rule 'if the next letter is a consonant, a root starts; if it is a vowel, a grammatical form starts'. "
      "Each cell is `shape count`, and the three values are `no filter / zipf < 3.0 / zipf < 2.0` (the shape with the most forms can differ by filter).")
    a("")
    rows = []
    for cname, c in des["combos"].items():
        for lv in MAIN_LEVELS:
            d = c["levels"][lv]
            cell_r = " / ".join(f"{d[f]['root_shape']} {d[f]['roots']:,}" for f in FILTERS)
            cell_g = " / ".join(f"{d[f]['gram_shape']} {d[f]['gram']:,}" for f in FILTERS)
            rows.append([f"{COMBO_LABEL[cname]} ({VARIANT_LABEL[c['root_variant']]} + {VARIANT_LABEL[c['gram_variant']]})" if lv == "all7" else "",
                         LEVEL_LABEL[lv], cell_r, cell_g])
    L += md_table(["Design (root spelling + grammatical spelling)", "Agreement level", "Roots", "Grammatical forms"], rows, "llll")
    a("")
    a("### 1.2 Spaced designs: pools that combine shapes of different lengths")
    a("")
    a("The space marks the boundary, so shapes of different lengths can be mixed. Each cell is `no filter / zipf < 3.0 / zipf < 2.0`.")
    a("")
    rows = []
    for var in ["space", "space_cap"]:
        p = des["pools_variable_length"][var]
        for lv in MAIN_LEVELS + ["le2_all7"]:
            rows.append([VARIANT_LABEL[var] if lv == "all7" else "", LEVEL_LABEL[lv],
                         " / ".join(f"{p['root'][lv][f]:,}" for f in FILTERS),
                         " / ".join(f"{p['gram'][lv][f]:,}" for f in FILTERS)])
    L += md_table(["Spelling", "Agreement level", "Root pool", "Grammatical pool"], rows, "llrr")
    a("")

    a("### 1.3 Per tokenizer (zipf < 3.0, single token)")
    a("")
    a("Number of single-token forms that pass the word filter (zipf < 3.0), looking at one tokenizer at a time. "
      "The claude_legacy row is the Claude proxy.")
    a("")
    cols = [("root", "space", None, "Root pool ␣kat"), ("root", "bare", "CVC", "CVC kat"), ("root", "space", "CVC", "CVC ␣kat"),
            ("root", "space", "CVCC", "CVCC ␣kat"), ("gram", "bare", "VCC", "VCC kat"), ("gram", "bare", "VCVC", "VCVC kat"),
            ("gram", "space", None, "Grammatical pool ␣kat")]
    rows = []
    for n in NAMES:
        r = [n]
        for role, var, shape, _ in cols:
            if shape is None:
                r.append(f"{des['pools_variable_length'][var][role]['per_tokenizer'][n]['lt3']:,}")
            else:
                r.append(f"{stats[shape][var]['per_tokenizer'][n]['lt3']:,}")
        rows.append(r)
    L += md_table(["Tokenizer"] + [c[3] for c in cols], rows)
    a("")

    # ---- 2. compromises
    a("## 2. Size of the compromises")
    a("")
    a("### 2.1 Changing the word-filter threshold")
    a("")
    a("Number of forms that are single tokens on all 7. The upper row uses the maximum over the 11 languages; "
      "the lower row (en) uses the English zipf only.")
    a("")
    cuts = ["< " + (f"{c:.1f}") if c != math.inf else "no filter" for c in SWEEP]
    rows = []
    for shape, var in [("VC", "bare"), ("VCV", "bare"), ("VCC", "bare"), ("VC", "space"), ("VCC", "space"),
                       ("CVC", "bare"), ("CVC", "space"), ("CCV", "space"), ("CVCV", "space"),
                       ("CCVC", "bare"), ("CVCC", "space"), ("CVCVC", "space")]:
        sw = stats[shape][var]["zipf_sweep"]
        rows.append([f"{shape} {VARIANT_LABEL[var]}", "11 languages"] + [f"{x:,}" for x in sw["max11"]["all7"]])
        rows.append(["", "en"] + [f"{x:,}" for x in sw["en"]["all7"]])
    L += md_table(["Shape, spelling", "Filter languages"] + cuts, rows, "ll" + "r" * len(cuts))
    a("")
    a("### 2.2 Allowing '2 tokens or fewer' instead of a single token")
    a("")
    a("Number of forms that take 2 tokens or fewer on all 7 (`no filter / zipf < 3.0 / zipf < 2.0`).")
    a("")
    rows = []
    for shape in ["VC", "VCV", "VCC", "CVC", "CCV", "CVCV", "CCVC", "CVCC"]:
        rows.append([shape] + [" / ".join(f"{stats[shape][v]['agreement']['le2_all7'][f]:,}" for f in FILTERS) for v in VARIANTS])
    L += md_table(["Shape"] + [VARIANT_LABEL[v] for v in VARIANTS], rows, "lrrrr")
    a("")
    a(f"### 2.3 Picking the cheapest {TARGET_ROOTS:,} roots / {TARGET_GRAM} grammatical forms that pass the filter")
    a("")
    a("Candidates that pass the word filter (zipf < 3.0) were sorted by token cost (number of tokenizers on which the form "
      "is not a single token → total tokens over the 7). "
      f"Then {TARGET_ROOTS:,} roots and {TARGET_GRAM} grammatical forms were picked, and the mean number of tokens per form was measured. "
      "`pool` combines all shapes of a role and can be used only in spaced designs. `Candidates` is the number of forms that pass the filter "
      "(for CCVC, CVCC and CVCVC, only forms whose frequency was measured are counted, that is, forms that are a single token somewhere "
      "or take 2 tokens or fewer on all 7). "
      "The seven columns on the right are the mean number of tokens of the picked forms.")
    a("")
    rows = []
    for var in ["bare", "space", "space_cap"]:
        for key in ["root:CVC:lt3", "root:CVCV:lt3", "root:CVCC:lt3", "root:CVCVC:lt3", "root:pool:lt3",
                    "gram:VC:lt3", "gram:VCV:lt3", "gram:VCC:lt3", "gram:VCVC:lt3", "gram:pool:lt3"]:
            d = des["best_n"][var][key]
            role, sh, _ = key.split(":")
            if not d.get("picked") or (sh == "pool" and not var.startswith("space")):
                continue  # with a glued spelling, mixing shapes of different lengths makes the text impossible to split
            rows.append([VARIANT_LABEL[var], ("root " if role == "root" else "grammatical ") + ("pool" if sh == "pool" else sh),
                         f"{d['available']:,}", f"{d['picked']:,}", f"{d['all7_single']:,}", f"{d['le2_all7']:,}"]
                        + [f"{d['mean_tokens'][n]:.2f}" for n in NAMES])
    L += md_table(["Spelling", "Candidate pool", "Candidates", "Picked", "Single on all 7", "≤2 on all 7"] + NAMES, rows,
                  "ll" + "r" * (4 + len(NAMES)))
    a("")
    a("### 2.4 Single-token forms are more often real words")
    a("")
    a("Number of forms and the share (%) with zipf ≥ 3.0, by the number of tokenizers (k) on which the form is a single token "
      "(`forms (share)`).")
    a("")
    rows = []
    for shape in ["VC", "VCV", "CVC", "CCV", "CVCV"]:
        for var in ["bare", "space"]:
            m = mech[shape][var]
            rows.append([f"{shape} {VARIANT_LABEL[var]}"] + [f"{m[str(k)]['n']:,} ({pct(m[str(k)]['word_ge3_share'])})" if str(k) in m else "-"
                                                           for k in range(len(NAMES) + 1)])
    L += md_table(["Shape, spelling"] + [f"k={k}" for k in range(len(NAMES) + 1)], rows)
    a("")

    a("### 2.5 Single tokens that pass the filter are mostly word fragments")
    a("")
    a(f"We collected the {frag['n_frequent_words']:,} words with zipf ≥ 3.0 in the 11 languages (duplicates across languages removed) "
      "and measured the share (%) of zipf < 3.0 forms that are a proper prefix of those words "
      "(␣ spelling: a fragment from the start of a word, e.g. ` calc` ← calculate) or "
      "a proper substring (glued spelling: a fragment inside a word, e.g. `ated` ← created). "
      "The baseline is the set of forms of the same shape that are a single token on no tokenizer "
      "(only shapes where every form's frequency was measured).")
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
    L += md_table(["Shape, spelling", "Single on all 7 & < 3.0", "Fragment %", "Not single & < 3.0", "Fragment %",
                   "Non-fragment forms single on all 7 (up to 10)"],
                  rows, "lrrrrl")
    a("")

    # ---- 3. method
    a("## 3. Method and checks")
    a("")
    a("- Vowels V = aeiou, consonants C = the other 21 letters (including y). Every possible form of each shape was generated.")
    a("- Leading-space spellings were appended after `the` and glued spellings after `1`, then tokenized, and the tokens after the context were counted. "
      "If the context and the form merged into one token, the form counted as not a single token.")
    a("  - Reason: mistral_sp (SentencePiece) adds a dummy space at the start of the input. So measuring `kat` alone in effect measures `␣kat`, "
      "and measuring `␣kat` alone measures a form with two spaces. With a context, the measurement reflects the form as it actually appears mid-sentence.")
    a("  - Glued-spelling values are for 'the form at the start of a run of letters'. When letters run on, as in `katenmirob`, "
      "a form can be cut together with neighboring letters; this experiment did not measure that (E2 does).")
    a("  - The pre-tokenization regexes of o200k, llama4 and mistral_tekken split before a capital letter, so each morpheme in `KatEnMirOb` "
      "is tokenized under the same condition as the `Kat` spelling value. "
      "cl100k, llama3 and claude_legacy do not split at case boundaries.")
    a("- Word filter: wordfreq `zipf_frequency` was measured in the 11 languages and the maximum was used. "
      "Capitalized spellings are also filtered by the frequency of the lowercase form.")
    a("- Agreement levels: " + ", ".join(f"`{LEVEL_LABEL[lv]}`" for lv in LEVELS) + ". `6 or more of 7` allows any one tokenizer to miss.")
    a("- claude_legacy is the tokenizer from the Claude 2 era. The current Claude tokenizer is not public, so claude_legacy serves only as a proxy.")
    a("")
    a("**Check 1: number of forms, over all of CVC + VC, where the single-token verdict differs between the in-context and standalone measurements**")
    a("")
    rows = [[VARIANT_LABEL[v]] + [f"{sanity_res['context_vs_standalone_CVC_VC'][v][n]['single_token_disagree']:,}" for n in NAMES]
            for v in VARIANTS]
    L += md_table(["Spelling"] + NAMES, rows)
    a("")
    a("**Check 2: number of forms, over all shapes, that merged with the context token** (0 means the context did not affect the form)")
    a("")
    rows = [[VARIANT_LABEL[v]] + [f"{sanity_res['merged_with_context_all_shapes'][v][n]:,}" for n in NAMES] for v in VARIANTS]
    L += md_table(["Spelling"] + NAMES, rows)
    a("")

    # ---- 4. per tokenizer
    a("## 4. Single-token counts by shape and spelling (per tokenizer, no filter)")
    a("")
    rows = []
    for shape in SHAPES:
        for var in VARIANTS:
            st = stats[shape][var]
            rows.append([shape if var == "bare" else "", VARIANT_LABEL[var], f"{st['n_forms']:,}"]
                        + [f"{st['per_tokenizer'][n]['none']:,}" for n in NAMES])
    L += md_table(["Shape", "Spelling", "Total"] + NAMES, rows, "ll" + "r" * (1 + len(NAMES)))
    a("")

    a("## 5. Agreement level × word filter")
    a("")
    a("Cells are in the order `no filter / zipf < 3.0 / zipf < 2.0`. `Pass filter` is the number of forms that pass the word filter "
      "regardless of tokenization (`-` for large shapes where frequency was measured for only some forms).")
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
    L += md_table(["Shape", "Spelling", "Total", "Pass filter (< 3.0 / < 2.0)"] + [LEVEL_LABEL[lv] for lv in LEVELS], rows,
                  "ll" + "r" * (2 + len(LEVELS)))
    a("")
    a("**For forms that are single tokens on exactly 6 of 7, the one tokenizer that failed** (no filter)")
    a("")
    rows = []
    for shape in ["CV", "VC", "VCV", "VCC", "CCV", "CVC", "CVCV", "CVCC"]:
        for var in VARIANTS:
            o = stats[shape][var]["odd_one_out_in_6of7"]
            rows.append([shape if var == "bare" else "", VARIANT_LABEL[var]] + [f"{o[n]:,}" for n in NAMES])
    L += md_table(["Shape", "Spelling"] + NAMES, rows, "ll" + "r" * len(NAMES))
    a("")

    # ---- 6. productivity by letter
    a("## 6. Productivity by letter")
    a("")
    a("Single-token share (%) in CVC when the consonant is in the first position (C1) or the last position (C2). "
      "`mean` is the mean single-token share over the 7, `6+` is the share that is a single token on 6 or more of 7, "
      "and `claude` is the claude_legacy share. "
      "Rows are sorted by the sum of C1 6+ and C2 6+, largest first. No word filter is applied.")
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
        L += md_table(["Consonant", "C1 mean", "C1 6+", "C1 claude", "C2 mean", "C2 6+", "C2 claude"], rows)
        a("")
    a("**Vowels** (CVC by its middle vowel, VC and CV by the vowel they contain; share (%) of those forms that are single tokens on 6 or more of 7)")
    a("")
    cs, cb = letters["CVC"]["space"], letters["CVC"]["bare"]
    rows = [[v, pct(cs["1V"][v]["mean_rate"]), pct(cs["1V"][v]["ge6_rate"]), pct(cb["1V"][v]["mean_rate"]), pct(cb["1V"][v]["ge6_rate"]),
             pct(letters["VC"]["bare"]["0V"][v]["ge6_rate"]), pct(letters["VC"]["space"]["0V"][v]["ge6_rate"]),
             pct(letters["CV"]["bare"]["1V"][v]["ge6_rate"]), pct(letters["CV"]["space"]["1V"][v]["ge6_rate"])] for v in VOWELS]
    L += md_table(["Vowel", "CVC␣ mean", "CVC␣ 6+", "CVC mean", "CVC 6+", "VC 6+", "VC␣ 6+", "CV 6+", "CV␣ 6+"], rows)
    a("")
    a("**Consonants in VC / CV** (share (%) that are single tokens on 6 or more of 7; only consonants not at 100)")
    a("")
    rows = []
    for c in CONSONANTS:
        vals = [letters["VC"]["bare"]["1C"][c]["ge6_rate"], letters["VC"]["space"]["1C"][c]["ge6_rate"],
                letters["CV"]["bare"]["0C"][c]["ge6_rate"], letters["CV"]["space"]["0C"][c]["ge6_rate"]]
        if any(v < 1 for v in vals):
            rows.append([c] + [pct(v) for v in vals])
    L += md_table(["Consonant", "VC", "VC␣", "CV", "CV␣"], rows)
    a("")
    cs_ = letters["CVC"]["space"]
    score = {c: (cs_["0C"][c]["ge6_rate"] + cs_["2C"][c]["ge6_rate"]) / 2 for c in CONSONANTS}
    ranked = sorted(CONSONANTS, key=lambda c: (-score[c], c))
    v_rate = {v: cs_["1V"][v]["ge6_rate"] for v in VOWELS}
    vr = sorted(VOWELS, key=lambda v: (-v_rate[v], v))
    drop = [c for c in CONSONANTS if cs_["0C"][c]["ge6_rate"] - cs_["2C"][c]["ge6_rate"] >= 0.2]
    a(f"In CVC ␣kat, the consonants with the highest 6+ share (mean of C1 and C2) are {', '.join(f'{c} {pct(score[c])}%' for c in ranked[:6])}, "
      f"and the lowest are {', '.join(f'{c} {pct(score[c])}%' for c in ranked[-6:])}. "
      f"Vowels rank {', '.join(f'{v} {pct(v_rate[v])}%' for v in vr)}. "
      f"Consonants whose 6+ share in the last position (C2) is at least 20 percentage points lower than in the first position (C1): {', '.join(drop) or 'none'}.")
    a("")
    a("Per-tokenizer letter shares are in `letters` in inventory.json.")
    a("")

    # ---- 7. reduced consonant set
    a("## 7. Shrinking the consonant set")
    a("")
    a("Consonants were removed one at a time, starting with the one whose removal loses the fewest CVC forms that are single tokens "
      "at the given agreement level (no word filter). "
      "`Yield` is the share of single-token forms among all CVC forms that the remaining consonants can make; "
      "`Of which < 3.0` is the number that pass the word filter.")
    a("")
    for key, steps in reduced.items():
        a(f"**{key}**")
        a("")
        rows = [[s["k"], s["removed"] or "-", f"{s['single']:,}", f"{s['total']:,}", pct(s["yield"]), f"{s['single_lt3']:,}"]
                for s in steps if s["k"] >= 10]
        L += md_table(["Consonants", "Removed", "Single token", "All CVC", "Yield %", "Of which < 3.0"], rows)
        a("")
    a("**Proposal (criterion: the smallest set that keeps at least 95% of the single-token forms)**")
    a("")
    for key, steps in reduced.items():
        full = steps[0]
        s = [x for x in steps if x["single"] >= 0.95 * full["single"]][-1]
        gone = "".join(sorted(set(CONSONANTS) - set(s["set"])))
        a(f"- {key}: {s['k']} consonants `{s['set']}` (removed `{gone or '-'}`) → single tokens {s['single']:,}/{full['single']:,}, "
          f"yield {pct(full['yield'])}% → {pct(s['yield'])}%, pass word filter {full['single_lt3']:,} → {s['single_lt3']:,}")
    a("")
    a("Shrinking the consonant set does not increase the absolute number of single-token forms. If forms are picked from a list, "
      "shrinking gains nothing in count; the only gains are a shorter spec and possibly less boundary instability in glued strings "
      "(to be checked in E2).")
    a("")

    # ---- 8. list preview
    a("## 8. Form list preview")
    a("")
    a("The full lists are in `lists` in inventory.json (shape → spelling → `all7_lt3`, `no_sp_lt3`, `ge6_lt3`; each entry is [form, max zipf]). "
      "Below are the first 40 in alphabetical order.")
    a("")
    for shape, var, lv in [("VC", "bare", "all7"), ("VCV", "bare", "all7"), ("VCC", "bare", "all7"), ("VCVC", "bare", "all7"),
                           ("CVC", "bare", "all7"), ("CVC", "space", "all7"), ("CVC", "space", "no_sp"),
                           ("CVCC", "space", "all7"), ("CCVC", "bare", "all7"), ("CVCVC", "space", "all7")]:
        items = [f for f, _ in lists[shape][var][f"{lv}_lt3"]]
        a(f"- {shape} {VARIANT_LABEL[var]}, {LEVEL_LABEL[lv]}, zipf < 3.0 ({len(items)} forms): " + (" ".join(items[:40]) or "none"))
    a("")

    a("## 9. Limitations")
    a("")
    a("- The current Claude tokenizer is not public. There is no guarantee that claude_legacy results apply as is to current Claude.")
    a("- Only single-token status was measured. Whether morpheme boundaries match token boundaries inside glued strings was not measured (E2).")
    a("- The word filter looks only at frequencies in 11 languages. Overlaps with romanized Korean, Japanese or Chinese, abbreviations, "
      "trademarks and programming identifiers are not filtered out.")
    a("- For short letter strings, wordfreq also counts the frequency of abbreviations, names and fragments of other languages. "
      "So the shorter the shape, the more forms the filter removes, and zipf ≥ 3.0 does not guarantee that every such form carries "
      "a strong meaning for an LLM. The actual size of semantic interference cannot be measured without a model API.")
    a("- Even a single token can be tied to a specific meaning in the training data (a name, an abbreviation, a code fragment). "
      "This experiment cannot measure that either.")
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
        "filters": {"none": "no filter", "lt3": "max zipf < 3.0", "lt2": "max zipf < 2.0"},
        "levels": LEVEL_LABEL,
        "targets": {"roots": TARGET_ROOTS, "gram": TARGET_GRAM},
        "n_forms_with_zipf": len(zipf),
        "notes": [
            "Token counts are measured with the form appended after a context: 'the' for leading-space spellings, '1' for glued spellings.",
            "The tokens strings in forms give the token count per tokenizer in meta.tokenizers order (9 or more is shown as 9, x = merged with the context).",
            "forms includes only forms that are a single token on at least one tokenizer in some spelling. All other forms take 2 or more tokens on every tokenizer and spelling.",
            "Entries in lists are [form (lowercase), max zipf], and only forms with max zipf < 3.0 are included. Build the spellings with meta.variants.",
            "zipf was measured only for forms that are a single token on at least one tokenizer or take 2 tokens or fewer on all 7, and for every form of shapes with 11,025 forms or fewer.",
            "Keys of designs.best_n are 'role:shape:filter'; the shape 'pool' combines all shapes of that role.",
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
