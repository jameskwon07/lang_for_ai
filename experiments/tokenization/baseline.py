"""E3 baseline: how many tokens AI-to-AI messages take when written in existing notations.

The 40 messages in `corpus/ai_messages.json`, each written in four variants, are counted with 7 tokenizers.
This experiment sets the token cost of the opponents (baselines) that this language has to beat.

Variants (each carries the same information)
- en       : concise English that a capable agent would write. The reference (denominator) for ratios.
- en_terse : terse English that another LLM understands without a spec (articles and copulas dropped, abbreviations, symbols).
             The strongest competitor that needs no spec. Abbreviations were used only where they actually cut tokens.
- ko       : natural Korean
- json     : compact JSON that a developer might pass between agents (short keys, no whitespace)
- oracle_min (derived) : for each message, the lowest token count among en, en_terse and json. The after-the-fact best of the notations that need no spec.

Each message is treated as sent on its own: tokens are counted per message and summed. Extra tokens such as chat templates or message headers are not counted.

Escape detection (heuristic on en: things this language would have to quote verbatim in their original spelling)
- url        : strings that start with http(s)://
- number     : words that contain a digit
- identifier : words with letters that contain / _ . inside, end in parentheses (), or are camelCase (file names, paths, code identifiers).
               A version made only of digits (3.11) counts only as number.
- proper     : words that start with a capital letter and are not at the start of a sentence (except I). All-caps abbreviations
               (SQL, API, HTTP, GPU, ID) are treated as ordinary vocabulary of this language and are not counted.

Statistics
- median, p90 : distribution over the 40 messages. p90 is the 9th value of statistics.quantiles(n=10, method="inclusive").
- ratio_total : variant total / en total
- ratio_msg   : distribution (median, p90) of (variant / en) computed for each message

There is no randomness, so the results are always the same.

Usage
    python3 baseline.py      # writes results/baseline.json and results/baseline.md
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
ALIGNMENT_JSON = HERE / "results" / "alignment.json"  # E2 result (used for the morpheme budget if present)

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


# ---------------------------------------------------------------- corpus

def load_corpus() -> list[dict]:
    """Read the corpus and check its format."""
    msgs = json.loads(CORPUS.read_text(encoding="utf-8"))
    assert isinstance(msgs, list) and len(msgs) == N_EXPECTED, f"need {N_EXPECTED} messages: {len(msgs)}"
    ids = set()
    for m in msgs:
        assert list(m.keys()) == FIELDS, f"{m.get('id')}: fields are not {FIELDS}"
        assert m["id"] not in ids, f"duplicate id: {m['id']}"
        ids.add(m["id"])
        assert m["category"] in CATEGORIES, f"{m['id']}: unknown category {m['category']}"
        compact = json.dumps(json.loads(m["json"]), separators=(",", ":"), ensure_ascii=False)
        assert compact == m["json"], f"{m['id']}: json field is not compact JSON"
    return msgs


def escape_kinds(text: str) -> list[str]:
    """Find the kinds of elements in an en sentence that need escaping (verbatim quoting). Uses the heuristic in the module docstring."""
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


# ---------------------------------------------------------------- statistics

def p90(xs: list[float]) -> float:
    return statistics.quantiles(xs, n=10, method="inclusive")[-1]


def dist(xs: list[float]) -> dict:
    return {"mean": statistics.mean(xs), "median": statistics.median(xs), "p90": p90(xs),
            "min": min(xs), "max": max(xs)}


def summarize(counts: dict[str, dict[str, int]], ids: list[str], chars: dict[str, dict[str, int]]) -> dict:
    """Per-variant summary for one tokenizer. counts[variant][id] = token count."""
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
    """Read the E2 tokens/morpheme values for W2_spaced + token_picked. None if they are not available."""
    if not ALIGNMENT_JSON.exists():
        return None
    try:
        data = json.loads(ALIGNMENT_JSON.read_text(encoding="utf-8"))
        return {r["tokenizer"]: r["tokens_per_morpheme"] for r in data["results"]
                if r.get("design") == "W2_spaced" and r.get("inventory") == "token_picked"} or None
    except (KeyError, TypeError, ValueError):
        return None


# ---------------------------------------------------------------- measurement

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


# ---------------------------------------------------------------- report

def _f(x: float, d: int = 2) -> str:
    return f"{x:.{d}f}"


def _pct(x: float) -> str:
    return f"{x * 100:+.0f}%"


def write_md(res: dict, msgs: list[dict]) -> str:
    names = list(res["per_tokenizer"])
    pt, cs, cross = res["per_tokenizer"], res["corpus_stats"], res["cross_tokenizer"]
    L: list[str] = []
    w = L.append

    w("# E3 baseline: token cost of the AI message corpus")
    w("")
    w("This summary was generated by `baseline.py`. Every number was measured by this script, and the raw data is in `baseline.json`. "
      f"The corpus is `{res['meta']['corpus']}` ({res['meta']['n_messages']} messages).")
    w("")

    # 0. Summary
    w("## 0. Summary")
    w("")
    items: list[str] = []
    en_tot = {n: pt[n]["en"]["total"] for n in names}
    lo_n, hi_n = min(en_tot, key=en_tot.get), max(en_tot, key=en_tot.get)
    items.append(f"**en baseline**: the 40 messages total {en_tot[lo_n]} ({lo_n}) to {en_tot[hi_n]} ({hi_n}) tokens; "
                 f"on o200k, mean {_f(pt['o200k']['en']['mean'], 1)}, median {_f(pt['o200k']['en']['median'], 1)}, "
                 f"p90 {_f(pt['o200k']['en']['p90'], 1)} tokens per message.")
    for v, label in [("en_terse", "en_terse (terse English, the strongest competitor without a spec)"), ("ko", "ko (Korean)"), ("json", "json (compact JSON)")]:
        c = cross[v]
        items.append(f"**{label}**: total ratio vs en {_f(c['ratio_total_min'])} ({c['argmin']}) to {_f(c['ratio_total_max'])} "
                     f"({c['argmax']}), 7-tokenizer mean {_f(c['ratio_total_mean'])}. o200k {_f(pt['o200k'][v]['ratio_total'])}, "
                     f"claude_legacy {_f(pt['claude_legacy'][v]['ratio_total'])}. "
                     f"Share of messages with fewer tokens than en (o200k) {pt['o200k'][v]['share_below_en'] * 100:.0f}%.")
    c = cross["oracle_min"]
    items.append(f"**oracle_min** (per message, the minimum of en / en_terse / json): ratio vs en {_f(c['ratio_total_min'])}–"
                 f"{_f(c['ratio_total_max'])}, mean {_f(c['ratio_total_mean'])}. "
                 "Number of times each variant gave the minimum (280 cells of message × tokenizer; ties all counted): "
                 + ", ".join(f"{v} {k}" for v, k in res["oracle_pick_counts"].items()) + ".")
    e_with = statistics.mean(res["by_escape"][n]["with_escape"]["ratio_total"]["en_terse"] for n in names)
    e_wo = statistics.mean(res["by_escape"][n]["without_escape"]["ratio_total"]["en_terse"] for n in names)
    j_with = statistics.mean(res["by_escape"][n]["with_escape"]["ratio_total"]["json"] for n in names)
    j_wo = statistics.mean(res["by_escape"][n]["without_escape"]["ratio_total"]["json"] for n in names)
    n_esc = len(cs["escape_ids"])
    items.append(f"**{n_esc} messages with escape targets (numbers, paths, identifiers, URLs, proper nouns) vs {40 - n_esc} without** "
                 f"(ratio vs en, 7-tokenizer mean): en_terse {_f(e_with)} vs {_f(e_wo)}, json {_f(j_with)} vs {_f(j_wo)}. "
                 f"Mean en tokens per message on o200k {_f(res['by_escape']['o200k']['with_escape']['mean']['en'], 1)} vs "
                 f"{_f(res['by_escape']['o200k']['without_escape']['mean']['en'], 1)}.")
    goal = (f"**Target line for this language**: to beat en_terse, which is readable without a spec, the mean tokens per message must be below "
            f"o200k {_f(pt['o200k']['en_terse']['mean'], 1)}, claude_legacy {_f(pt['claude_legacy']['en_terse']['mean'], 1)} "
            f"(en is {_f(pt['o200k']['en']['mean'], 1)} / {_f(pt['claude_legacy']['en']['mean'], 1)}).")
    budget = res["morpheme_budget"]
    if budget and "o200k" in budget and "claude_legacy" in budget:
        goal += (f" Converted with the E2 tokens/morpheme for W2_spaced + token_picked, that means fewer than "
                 f"o200k {_f(budget['o200k']['morphemes_per_msg_to_match_en_terse'], 1)}, "
                 f"claude_legacy {_f(budget['claude_legacy']['morphemes_per_msg_to_match_en_terse'], 1)} morphemes per message (section 7).")
    goal += " The cost of putting the spec (thousands of tokens) in the context is not included in this comparison."
    items.append(goal)
    for k, it in enumerate(items, 1):
        w(f"{k}. {it}")
    w("")

    # 1. Corpus
    w("## 1. Corpus")
    w("")
    w("Messages per category: " + ", ".join(f"{c} {k}" for c, k in cs["categories"].items()) + ".")
    w("")
    hist = cs["sentences_en"]["histogram"]
    w("Sentences per en message (sentences: messages): " + ", ".join(f"{k}: {v}" for k, v in hist.items())
      + f" (median {_f(cs['sentences_en']['median'], 1)}, mean {_f(cs['sentences_en']['mean'], 2)}). "
      "Sentences are counted as . ? ! followed by a space or the end of the text.")
    w("")
    w("| Variant | Total chars | Median per message | p90 | Min | Max |")
    w("|---|---:|---:|---:|---:|---:|")
    for v in VARIANTS:
        d = cs["chars"][v]
        w(f"| {v} | {d['total']} | {_f(d['median'], 1)} | {_f(d['p90'], 1)} | {d['min']} | {d['max']} |")
    w("")
    w("Writing guidelines")
    w("")
    w("- The four variants carry the same information. Small numbers are written as words (five) in en and as digits in en_terse and json.")
    w("- en_terse drops articles and copulas and uses symbols such as `->`, `=`, `+`, `~`, `;`. Abbreviations were kept only when measuring them with the tokenizers showed they did not add tokens "
      "(for example, `w/`, `Ctx`, `2nd`, `O(n^2)` take more tokens than `with`, `Context`, `second`, `quadratic`, so they were not used).")
    w("- json uses short keys and serialization without whitespace (`separators=(',', ':')`), and most values are snake_case. Proper nouns and URLs are kept as in the original.")
    w("- ko is natural Korean. Foreign names of people and places are transliterated into Hangul; paths, identifiers and URLs are kept as in the original.")
    w("- The only real service URL is the Python documentation. The other names (people, the repository example-org/tilemap) are fictional.")
    w("")
    w(f"Messages with escape targets ({n_esc}/40, heuristic on en; messages per kind: "
      + ", ".join(f"{k} {v}" for k, v in cs["escape_kind_counts"].items()) + ")")
    w("")
    w("| id | Category | Kinds |")
    w("|---|---|---|")
    cat_of = {m["id"]: m["category"] for m in msgs}
    for i, k in cs["escape_kinds"].items():
        w(f"| {i} | {cat_of[i]} | {', '.join(k)} |")
    w("")

    # 2. Totals and ratios
    w("## 2. Totals by tokenizer and ratio vs en")
    w("")
    w("Cell = total tokens over the 40 messages (ratio vs the en total). chars/token is for en.")
    w("")
    w("| Tokenizer | en | en_terse | ko | json | oracle_min | en chars/token |")
    w("|---|---:|---:|---:|---:|---:|---:|")
    for n in names:
        cells = [str(pt[n]["en"]["total"])] + [f"{pt[n][v]['total']} ({_f(pt[n][v]['ratio_total'])})" for v in ALL_VARIANTS[1:]]
        w(f"| {n} | " + " | ".join(cells) + f" | {_f(pt[n]['en']['chars_per_token'])} |")
    w("| **7-tokenizer mean ratio** | 1.00 | " + " | ".join(_f(cross[v]["ratio_total_mean"]) for v in ALL_VARIANTS[1:]) + " | |")
    w("")

    # 3. Distribution per message
    w("## 3. Distribution of tokens per message")
    w("")
    w("Cell = median / p90 (40 messages).")
    w("")
    w("| Tokenizer | " + " | ".join(ALL_VARIANTS) + " |")
    w("|---|" + "---:|" * len(ALL_VARIANTS))
    for n in names:
        w(f"| {n} | " + " | ".join(f"{_f(pt[n][v]['median'], 1)} / {_f(pt[n][v]['p90'], 1)}" for v in ALL_VARIANTS) + " |")
    w("")

    # 4. Distribution of per-message ratios
    w("## 4. Distribution of per-message ratios vs en")
    w("")
    w("Cell = median / p90 of (variant / en) computed for each message; in parentheses, the share of messages with fewer tokens than en.")
    w("")
    w("| Tokenizer | en_terse | ko | json | oracle_min |")
    w("|---|---:|---:|---:|---:|")
    for n in names:
        w(f"| {n} | " + " | ".join(
            f"{_f(pt[n][v]['ratio_msg_median'])} / {_f(pt[n][v]['ratio_msg_p90'])} ({pt[n][v]['share_below_en'] * 100:.0f}%)"
            for v in ALL_VARIANTS[1:]) + " |")
    w("")

    # 5. By category
    w("## 5. By category")
    w("")
    w("en is the mean tokens per message on o200k. The other columns are the mean over the 7 tokenizers of the total ratio within the category (variant / en).")
    w("")
    w("| Category | n | en (o200k mean) | en_terse | ko | json | oracle_min |")
    w("|---|---:|---:|---:|---:|---:|---:|")
    for c in CATEGORIES:
        bc = {n: res["by_category"][n][c] for n in names}
        w(f"| {c} | {bc['o200k']['n']} | {_f(bc['o200k']['mean']['en'], 1)} | "
          + " | ".join(_f(statistics.mean(bc[n]["ratio_total"][v] for n in names)) for v in ALL_VARIANTS[1:]) + " |")
    w("")

    # 6. Escape targets
    w("## 6. With and without escape targets")
    w("")
    w("Cell = mean tokens per message (total ratio vs en).")
    w("")
    w("| Tokenizer | Subset | n | en | en_terse | ko | json |")
    w("|---|---|---:|---:|---:|---:|---:|")
    for n in names:
        for key, label in [("with_escape", "with escapes"), ("without_escape", "without escapes")]:
            b = res["by_escape"][n][key]
            w(f"| {n} | {label} | {b['n']} | {_f(b['mean']['en'], 1)} | "
              + " | ".join(f"{_f(b['mean'][v], 1)} ({_f(b['ratio_total'][v])})" for v in ["en_terse", "ko", "json"]) + " |")
    w("")

    # 7. Target line
    w("## 7. Target line for this language")
    w("")
    w("To beat each baseline, this language must write the same messages in fewer tokens than shown below (mean per message).")
    w("")
    budget = res["morpheme_budget"]
    if budget:
        w("Dividing by the E2 (`alignment.json`) tokens/morpheme value for W2_spaced + token_picked gives the number of morphemes available per message. "
          "The E2 values were read from `alignment.json` as it was when this script ran.")
        w("")
        w("| Tokenizer | en | en_terse | oracle_min | E2 tokens/morpheme | Morpheme budget (= en) | Morpheme budget (= en_terse) |")
        w("|---|---:|---:|---:|---:|---:|---:|")
        for n in names:
            b = budget.get(n)
            tail = (f"{_f(b['tokens_per_morpheme_w2_token_picked'])} | {_f(b['morphemes_per_msg_to_match_en'], 1)} | "
                    f"{_f(b['morphemes_per_msg_to_match_en_terse'], 1)}") if b else "- | - | -"
            w(f"| {n} | {_f(pt[n]['en']['mean'], 1)} | {_f(pt[n]['en_terse']['mean'], 1)} | "
              f"{_f(pt[n]['oracle_min']['mean'], 1)} | {tail} |")
    else:
        w("(`alignment.json` was not found, so the morpheme budget was not computed.)")
        w("")
        w("| Tokenizer | en | en_terse | oracle_min |")
        w("|---|---:|---:|---:|")
        for n in names:
            w(f"| {n} | {_f(pt[n]['en']['mean'], 1)} | {_f(pt[n]['en_terse']['mean'], 1)} | {_f(pt[n]['oracle_min']['mean'], 1)} |")
    w("")

    # 8. Limitations
    w("## 8. Limitations")
    w("")
    w("- The corpus is 40 messages written by one model in one pass. The style may be skewed, and the sample is small, so the second decimal place of the ratios is not reliable.")
    w("- The author aligned the four variants to carry the same information, but no person or other model verified this. "
      "Whether en_terse is understood correctly without a spec could not be checked without a model API, so it was not measured.")
    w("- The current Claude tokenizer is not public. claude_legacy is a proxy.")
    w("- The abbreviations in en_terse were chosen by measuring with these tokenizers, so they are biased in the competitor's favor (on purpose).")
    w("- json is a fairly compact form with short keys and snake_case values. Real JSON between agents may cost more because of longer keys or whitespace.")
    w("- Escape detection is a heuristic. All-caps abbreviations are not counted.")
    w("- Extra message tokens such as chat templates and role markers, and the cost of the spec (context), were not counted.")
    w("")

    # Appendix
    w("## Appendix: tokens per message")
    w("")
    w("Cell = o200k / claude_legacy.")
    w("")
    w("| id | Category | en | en_terse | ko | json |")
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
