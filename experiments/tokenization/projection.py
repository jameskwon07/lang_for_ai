"""Projection: how many tokens AI messages actually take when written in the draft grammar.

corpus/gloss_1.json and gloss_2.json (morpheme analyses made independently by two estimators) are turned
into real strings and measured with 7 tokenizers. The spelling puts one space between morphemes (W2), and
morpheme forms are assigned so that the forms with the lowest mean token count for "leading space + form" go to the most frequent morphemes.

Scenarios that remove grammar devices one at a time (cumulative)
- S0 strict      : as the estimators wrote it (speech act, confidence and evidentiality, all 3 in every clause)
- S1 elided      : default values (assertion, high confidence, direct observation) are omitted
- S2 fused       : speech act, confidence and evidentiality are merged into one affix, which is omitted if all are default
- S3 positional  : agent, patient and theme role affixes are removed and shown by word order
- S4 no-linker   : the compound linker affix (LNK) and the modifier marker (ATR) are removed
- S5 raw-digits  : numbers are written as Arabic numerals as is (requires relaxing the alphabet-only rule)

Output: results/projection.json, results/projection.md
Usage: python3 projection.py
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
CONTEXT = "the"  # preceding context. Forms are measured after this context to avoid SentencePiece's dummy space
N_CLOSED = 150  # number of cheapest forms given first to affixes, markers, numbers and variables (closed classes)
ROOT_LEXICON = 1000  # assumed number of core roots
SCENARIOS = ["S0_strict", "S1_elided", "S2_fused", "S3_positional", "S4_no_linker", "S5_raw_digits"]

# Marker names for each estimator (the two estimators used different labels)
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
    """For each candidate form: token count per tokenizer (leading space included, in context) and word frequency."""
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
    """Gloss string -> list of labels. Verbatim text in quotes that contains spaces (RAW/STR) is kept as one item."""
    text = text.replace("|", " ")
    items = re.findall(r'(?:RAW|STR):"[^"]*"|\S+', text)
    return items


def realize(items: list[str], k: int, scenario: str) -> list[tuple[str, str]]:
    """Apply a scenario and build a list of (kind, value). Kinds: lex (morpheme), raw (verbatim text), digits (Arabic numerals)."""
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
            # collect the speech act, confidence and evidentiality group of one clause
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
            # drop the number marker and gather the digits into a string of Arabic numerals
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
    """Give cheap forms to frequent morphemes. Closed classes come first; roots are assumed to be spread evenly over a 1,000-root lexicon."""
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
            lex = build_lexicon(seqs, forms)  # each scenario gets its own lexicon, fitted to its grammar
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
    lines = ["# Projection: actual token cost of the draft grammar", "",
             "Generated by `projection.py`. The values were measured after turning the two estimators' morpheme analyses (corpus/gloss_1.json, gloss_2.json) into real strings in W2 spelling (one space between morphemes).", "",
             f"- Candidate forms: {r['meta']['n_candidate_forms']:,} ({', '.join(SHAPES)}, max zipf across 11 languages < 3.0)",
             f"- Closed classes (affixes, markers, numbers, variables) get the {r['meta']['n_closed_slots']} cheapest forms; roots are spread evenly over the next {r['meta']['root_lexicon']:,} forms",
             "- Mean tokens per form (leading space included, closed classes / roots): " + ", ".join(
                 f"{n} {r['meta']['form_cost_top']['closed_per_tokenizer'][n]:.2f} / {r['meta']['form_cost_top']['roots_per_tokenizer'][n]:.2f}" for n in names), "",
             "## Total tokens over the 40 messages and ratio vs English", ""]
    lines.append("| Estimator | Scenario | Morphemes/message | " + " | ".join(f"{n} (vs en·terse)" for n in focus) + " |")
    lines.append("|---|---|---|" + "---|" * len(focus))
    for k, per in r["glosses"].items():
        for scen, v in per.items():
            cells = [f"{v['tokens'][n]:,} ({v['ratio_vs_en'][n]:.2f}·{v['ratio_vs_en_terse'][n]:.2f})" for n in focus]
            lines.append(f"| {k} | {scen} | {v['morphemes_per_msg']:.1f} | " + " | ".join(cells) + " |")
    lines += ["", "Baseline totals: " + ", ".join(f"{n} en {r['baseline'][n]['en']:,} / terse {r['baseline'][n]['en_terse']:,}" for n in focus), "",
              "## Example (m01)", "", f"- en: {r['examples_m01']['en']}", f"- en_terse: {r['examples_m01']['en_terse']}"]
    for key in ("gloss_1", "gloss_2"):
        for scen in ("S0_strict", "S5_raw_digits"):
            lines.append(f"- {key} {scen}: `{r['examples_m01'][key][scen]}`")
    lines += ["", "## Limitations", "",
              "- Morpheme counts rely on analyses the two estimators made by hand. They will change once the actual grammar is fixed.",
              "- S3 (roles shown by word order) is an optimistic estimate that ignores the ambiguity when it combines with omitted arguments.",
              "- The root assignment assumes that 'the roots found in the corpus are spread evenly over a 1,000-root lexicon'.",
              "- The current Claude tokenizer is not public. claude_legacy is a proxy.",
              "- Whether an LLM actually reads and writes these strings correctly was not measured."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
