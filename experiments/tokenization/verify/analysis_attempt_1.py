"""Attempt 1 analysis: token accounting, macro reuse on the odd (non-encoded) messages, spec break-even.

Run from experiments/tokenization after verify/attempt_1.py:  python3 verify/analysis_attempt_1.py
Writes verify/analysis_attempt_1.json.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from toklib import load_all  # noqa: E402
import attempt_1 as A  # noqa: E402

# keywords (lower-case substrings of the en text) that signal the concept of each used phrase macro
MACRO_KEYWORDS = {
    "@return_top": ["most relevant", "top "], "@one_sentence_summary": ["one-sentence", "one sentence"],
    "@later_this_week": ["this week"], "@lit_search": ["literature"], "@no_blockers": ["blocker"],
    "@per": ["according to"], "@for_backcompat": ["backward compat"], "@not_found": ["does not exist", "not found"],
    "@my_prev_answer": ["previous answer", "my earlier answer"], "@in_order": ["first,", " then "],
    "@does_that_work": ["work for you", "ok with you", "does that work"], "@rest_correct": ["everything else"],
    "@gpu_hour": ["gpu hour"], "@likely_cause": ["likely cause"], "@conf_fair_tool": ["fairly confident"],
    "@conf_low": ["confidence is low", "low confidence"], "@context_next_agent": ["next agent"],
    "@pass_back": ["back to you"], "@needs_human_approval": ["human approval"],
}


def main() -> None:
    toks = load_all()
    names = list(toks)
    d = json.loads((HERE / "attempt_1.json").read_text())
    corpus = json.loads((HERE.parent / "corpus" / "ai_messages.json").read_text())
    even = [m for m in corpus if int(m["id"][1:]) % 2 == 0]
    odd = [m for m in corpus if int(m["id"][1:]) % 2 == 1]

    # 1. en_terse token classes
    terse_classes = {}
    for n in ("o200k", "claude_legacy", "mistral_sp"):
        c = {"word": 0, "punct_or_space": 0, "digit": 0}
        for m in even:
            for p in toks[n].pieces(m["en_terse"]):
                if re.search(r"[A-Za-z]", p):
                    c["word"] += 1
                elif re.search(r"[0-9]", p):
                    c["digit"] += 1
                else:
                    c["punct_or_space"] += 1
        terse_classes[n] = c

    # 2. own encoding: morphemes by class and tokens by class (each item measured with a preceding space)
    A.N_NUM = d["measurement"]["config"]["n_num"]
    macro_exp = {k: exp for k, _, _, exp in A.MACROS}
    lex_by_form = d["lexicon"]
    key_of_form = {}
    for k, v in d["measurement"]["used_form_cost"].items():
        key_of_form[v["form"]] = k
    mine_classes = {}
    for n in ("o200k", "claude_legacy", "mistral_sp"):
        c = {"grammar_markers": [0, 0], "phrase_macros": [0, 0], "roots": [0, 0], "number_forms": [0, 0],
             "raw_text": [0, 0]}
        for mid in sorted(A.MESSAGES):
            for kind, v in A.expand(A.dsl_tokens(A.MESSAGES[mid][0]), False, macro_exp):
                if kind == "raw":
                    cls = "raw_text"
                    cost = toks[n].count("the " + v) - toks[n].count("the")
                else:
                    form = d["measurement"]["used_form_cost"][v]["form"]
                    cost = d["measurement"]["used_form_cost"][v][n]
                    cls = ("phrase_macros" if v.startswith("@") else "grammar_markers" if v.startswith("_")
                           else "number_forms" if v.startswith("#") else "roots")
                c[cls][0] += 1
                c[cls][1] += cost
        mine_classes[n] = {k: {"items": a, "tokens_in_context": b} for k, (a, b) in c.items()}

    # 3. macro reuse: in how many of the 20 odd (not encoded) messages does each used macro's concept appear
    used_macros = [k for k in d["measurement"]["used_form_cost"] if k.startswith("@")]
    reuse = {}
    for k in used_macros:
        kws = MACRO_KEYWORDS.get(k, [])
        reuse[k] = {"even_messages": sum(1 for m in even if any(w in m["en"].lower() for w in kws)),
                    "odd_messages": sum(1 for m in odd if any(w in m["en"].lower() for w in kws)),
                    "odd_ids": [m["id"] for m in odd if any(w in m["en"].lower() for w in kws)],
                    "keywords": kws}

    # 4. break-even: spec tokens / saved tokens per message
    tot = d["measurement"]["totals"]
    spec = d["measurement"]["spec"]["spec_tokens"]
    breakeven = {}
    for n in names:
        saved = (tot[n]["en_terse"] - tot[n]["main"]) / 20
        breakeven[n] = {"saved_per_message": round(saved, 2), "spec_tokens": spec[n],
                        "messages_to_amortise_spec": (round(spec[n] / saved) if saved > 0 else None)}

    out = {"en_terse_token_classes_even20": terse_classes, "attempt_1_token_classes": mine_classes,
           "macro_reuse": reuse, "breakeven_vs_en_terse": breakeven}
    (HERE / "analysis_attempt_1.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
