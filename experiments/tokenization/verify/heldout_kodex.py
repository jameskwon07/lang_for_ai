"""Held-out test of KODEX-1 (attempt 1, codebook strategy, main config B_num10) on the ODD messages m01..m39.

Run from experiments/tokenization:  python3 verify/heldout_kodex.py
Writes verify/heldout_kodex.json only. Does not modify any existing file.

Method
- Grammar, lexicon, form pool, form assignment, macro handling, number expansion, rendering and token counting are
  the ones in verify/attempt_1.py (imported, not copied): attempt_1.evaluate() is called with config B_num10.
- Sanity check 1: the same call on the original even messages must reproduce attempt_1.json (totals, rendered
  messages) and attempt_1_spec.txt exactly, otherwise the script aborts.
- New entries (only where no faithful paraphrase with existing entries was found) are appended AFTER the last
  existing entry of the frozen priority order, in order of first use in m01..m39, so assign_forms() gives them the
  next unused pool forms (same related()/VETO filters). Sanity check 2: every pre-existing entry keeps its form.
- The DSL is the one of attempt_1.py: _X grammar, @x phrase macro, #n number, "raw text" quoted raw chunk(s),
  plain word = root.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import attempt_1 as A  # noqa: E402
from toklib import load_all  # noqa: E402
from forms_attempt_1 import load_pool  # noqa: E402

MAIN = "B_num10"

# ---------------------------------------------------------------- new entries (appended after the frozen lexicon)
# (key, gloss, first message, why no faithful paraphrase)
ADDITIONS = [
    ("exponential", "exponential", "m01",
     "'exponential backoff': increase/double paraphrases change the meaning (linear growth or base 2 only)"),
    ("integration", "integration", "m07",
     "'integration tests' (vs unit tests): no root for integration; combine/system test mean other things"),
    ("calendar", "calendar", "m15",
     "'calendar quarter' vs 'fiscal quarter' is the whole point of the question; 'quarter of year' is ambiguous"),
    ("loop", "loop", "m25",
     "code loop: no root (cycle/repeat would be misread as cyclic dependency / duplicated code)"),
    ("encyclopedia", "encyclopedia", "m33",
     "'2 encyclopedias' as cited sources: 'reference book' loses the source type"),
]

# concepts with no entry expressed with existing entries (plus structural choices a reviewer should see)
PARAPHRASES = [
    "m01 'Please' -> dropped: bare imperative is the request form; KODEX-1 has no politeness marker",
    "m01 'retry logic' -> retry code",
    "m01 'backoff' -> delay (exponential delay; 'exponential' is a new entry)",
    "m01 'at most 5' -> max 5",
    "m01 'to use' (purpose) -> CNT use ... (refactor X: use Y)",
    "m07 'before opening the pull request' -> THEN open-PR phrase (then open a pull request)",
    "m11 'calculator' -> calculation tool",
    "m11 'remaining margin' -> remaining budget (remain budget)",
    "m15 'fiscal' -> financial",
    "m15 'do you mean X or Y' -> YOU mean 'last quarter' IS X OR Y QUES",
    "m17 'in a row' -> straight (3 TIMES straight)",
    "m19 'translation' -> root translate (noun use under the one-root rule)",
    "m19 'exceeded' -> PAST go beyond",
    "m19 'chunks' -> part",
    "m19 'go ahead' -> proceed",
    "m21 'complaints' -> root complain (noun use under the one-root rule)",
    "m21 'frequency' -> root frequent (noun use under the one-root rule)",
    "m21 'would like' -> want",
    "m21 'a second reviewer' -> second review",
    "m21 'there' (= at that step) -> FOR IT",
    "m21 'within the hour' -> within 1 hour",
    "m23 'could' (suggestion) -> CAN",
    "m23 'revert' -> rollback (easy rollback = easy to revert)",
    "m25 'quadratic' -> raw O(n^2) (Q1 quote)",
    "m25 'dictionary' -> map",
    "m25 'keyed by ID' -> WITH ID key (ID as raw Q1 chunk)",
    "m25 'so consider' (imperative after 'so') -> CONSE YOU SHOULD consider (bare verb after CONSE would take the "
    "previous subject)",
    "m27 'paragraph' -> section",
    "m31 'disagree' -> NEG agree",
    "m31 'sensor' -> measure device",
    "m31 'deleting' -> remove",
    "m33 'capital of Australia' -> australian capital (root australian exists; no raw name needed)",
    "m35 'version 4.2.1' -> 4 POINT 2 POINT 1 (POINT used twice as a version separator; spec defines only a "
    "decimal point)",
    "m37 'the fix is on branch X' -> branch X WITH fix (clause-initial 'fix' would read as an imperative)",
    "m37 'one run in ten' -> 1 PER 10 run",
    "m39 'State so far' -> status so-far phrase (clause-initial 'state' would read as an imperative)",
    "m39 'both travelers' -> ALL 2 passenger",
    "m39 'euros' -> raw EUR (Q1 quote)",
    "m05/m25 '1,200', '3,000', '100,000' -> 12 HUNDRED, 3 THOUSAND, 100 THOUSAND (multipliers from the grammar)",
]

# ---------------------------------------------------------------- the 20 held-out messages (DSL, back-translation)
MESSAGES = {
    "m01": ('refactor retry code _IN "src/net/client.py" _CNT use exponential delay _WITH max #5 attempt _SEP '
            '@keep_unchanged public interface',
            "Refactor the retry code (logic) in src/net/client.py: use exponential delay (backoff) with max 5 "
            "attempts. Keep the public interface unchanged."),
    "m03": ('turn user question _TO sql query against sale database _AND run _IT _SEP report _ONLY result _NEG query',
            "Turn the user question into a SQL query against the sales database and run it. Report only the "
            "result, not the query."),
    "m05": ('_PAST process #12 _HUNDRED _OF #3 _THOUSAND record @so_far _SEP job _SHOULD finish _IN _APPROX #25 '
            'minute _AT current rate',
            "I processed 1,200 (12 hundred) of 3,000 records so far. The job should finish in about 25 minutes at "
            "the current rate."),
    "m07": ('_ALL unit test pass local _PROG wait _FOR integration test finish _THEN @open_pr',
            "All unit tests pass locally. I am waiting for the integration tests to finish, then (I) open a pull "
            "request."),
    "m09": ('search _PAST return #14 result _SEP _MOST relevant _IS official changelog _AT '
            '"https://docs.python.org/3/whatsnew/3.13.html" _IT list remove module',
            "The search returned 14 results. The most relevant (one) is the official changelog at "
            "https://docs.python.org/3/whatsnew/3.13.html; it lists the removed modules."),
    "m11": ('calculation tool confirm total cost within budget _BUT remain budget small',
            "The calculation tool (calculator) confirms the total cost is within budget, but the remaining budget "
            "(margin) is small."),
    "m13": ('summary _SHOULD target executive _OR engineer _QUES technical detail level depend _ON audience',
            "Should the summary target executives or engineers? The technical detail level depends on the "
            "audience."),
    "m15": ('_YOU mean "last quarter" _IS _MOST recent calendar quarter _OR company financial quarter _QUES',
            "Do you mean 'last quarter' is the most recent calendar quarter or the company's financial (fiscal) "
            "quarter?"),
    "m17": ('request _TO payment api _PAST fail #3 _TIMES straight _WITH http #503 _PAST stop retry _FOR avoid hit '
            'rate_limit',
            "The request to the payments API failed 3 times straight (in a row) with HTTP 503. I stopped retrying "
            "(in order) to avoid hitting the rate limit."),
    "m19": ('translate step _PAST fail _CAUSE input _PAST go beyond context limit _CAN split document _TO part _AND '
            'retry _SHOULD proceed _QUES',
            "The translation step failed because the input went beyond (exceeded) the context limit. I can split "
            "the document into parts (chunks) and retry. Should I proceed?"),
    "m21": ('_I propose #3 step _CNT collect customer complain _AND group _THEY _BY theme _AND rank theme _BY '
            'frequent _SEP group _IS _MOST hard step _CONSE _I want second review _FOR _IT _FUT start collect '
            'unless _YOU object _SEP expect _FIRST result within #1 hour',
            "I propose 3 steps: collect customer complaints, and group them by theme, and rank the themes by "
            "frequency. Grouping is the hardest step, so I want a second review for it (there). I will start "
            "collecting unless you object. Expect first results within 1 hour."),
    "m23": ('_INSTEAD whole module rewrite _WE _CAN add cache layer _IN front _OF slow query _SEP _THIS _IS lower '
            'risk _AND easy rollback',
            "Instead of a whole-module rewrite, we can (could) add a cache layer in front of the slow queries. "
            "This is lower risk and an easy rollback (easy to revert)."),
    "m25": ('patch correct _BUT loop _IN "merge_records()" _IS "O(n^2)" _IT _FUT _TOO slow _WITH #100 _THOUSAND row '
            '_CONSE _YOU _SHOULD consider map _WITH "ID" key',
            "The patch is correct, but the loop in merge_records() is O(n^2) (quadratic). It will be too slow with "
            "100 thousand rows, so you should consider a map (dictionary) with ID keys."),
    "m27": ('summary good overall _IT slight _TOO long _SEP background section cut _FUT bring _IT within limit',
            "The summary is good overall. It is slightly too long. Cutting the background section (paragraph) will "
            "bring it within the limit."),
    "m29": ('_I agree _YOUR plan _WITH #1 change _CNT run _MORE cheap model _FIRST _AND use larger _ONLY _FOR hard '
            'case',
            "I agree (with) your plan, with 1 change: run the cheaper model first and use the larger (one) only "
            "for (the) hard cases."),
    "m31": ('_I _NEG agree _WITH outlier drop _THEY come _FROM real measure device fault _CONSE _HORT flag _THEY '
            '_INSTEAD remove',
            "I do not agree (disagree) with dropping the outliers. They come from a real measuring-device (sensor) "
            "fault, so we should flag them instead of removing (deleting) them."),
    "m33": ('australian capital _IS "Canberra" _NEG "Sydney" @conf_high australian government website _AND #2 '
            'encyclopedia',
            "The Australian capital (capital of Australia) is Canberra, not Sydney. I am highly confident; "
            "(sources:) the Australian government website and 2 encyclopedias."),
    "m35": ('_YES bug _PAST _PASS fix _IN version #4.2 _POINT #1 _SEP changelog _AT '
            '"https://github.com/example-org/tilemap/blob/main/CHANGELOG.md" confirm _IT _AND _PAST reproduce fix '
            'local @conf_high',
            "Yes, the bug was fixed in version 4.2.1. The changelog at "
            "https://github.com/example-org/tilemap/blob/main/CHANGELOG.md confirms it, and I reproduced the fix "
            "locally. I am highly confident."),
    "m37": ('_PROG handoff _CNT branch "fix/login-timeout" _WITH fix _SEP remain work _CNT update "test_auth.py" '
            '_SEP flaky test _IS "test_session_expiry" _IT fail _APPROX #1 _PER #10 run',
            "I am handing off: branch fix/login-timeout has the fix. The remaining work: update test_auth.py. The "
            "flaky test is test_session_expiry; it fails about 1 per 10 runs."),
    "m39": ('status @so_far _CNT flight _TO "Lisbon" _PASS book _FOR _ALL #2 passenger _BUT _NEG hotel _SEP remain '
            'budget _IS #850 "EUR" _SEP user want stay near old town',
            "Status (state) so far: flights to Lisbon are booked for all 2 (both) passengers (travelers), but not "
            "the hotel. The remaining budget is 850 EUR (euros). The user wants to stay near the old town."),
}

# ---------------------------------------------------------------- pipeline hooks (append-only lexicon extension)
_orig_build_entries = A.build_entries
_orig_priority_order = A.priority_order


def build_entries_ext(**kw) -> list[dict]:
    entries = _orig_build_entries(**kw)
    have = {e["key"] for e in entries}
    for key, gloss, _, _ in ADDITIONS:
        if key in have:
            raise SystemExit(f"addition {key!r} already exists in the frozen lexicon")
        entries.append({"key": key, "section": "core", "gloss": gloss, "est_zipf": None, "expansion": None,
                        "class": None, "added": True})
    return entries


def priority_order_ext(entries: list[dict]) -> list[dict]:
    """frozen order of the original entries, then the additions in order of first use (never re-ranked)."""
    base = [e for e in entries if not e.get("added")]
    added = [e for e in entries if e.get("added")]
    return _orig_priority_order(base) + added


def run(messages: dict, ids: list[str], toks: dict, pool: list[dict], extended: bool) -> dict:
    saved = (A.MESSAGES, A.build_entries, A.priority_order)
    try:
        A.MESSAGES = messages
        if extended:
            A.build_entries, A.priority_order = build_entries_ext, priority_order_ext
        return A.evaluate(A.CONFIGS[MAIN], toks, pool, ids)
    finally:
        A.MESSAGES, A.build_entries, A.priority_order = saved


def main() -> None:
    toks = load_all()
    names = list(toks)
    pool = load_pool()
    corpus = {m["id"]: m for m in json.loads((HERE.parent / "corpus" / "ai_messages.json").read_text())}

    # sanity check 1: original even run is reproduced exactly
    even_ids = sorted(A.MESSAGES)
    ref = json.loads((HERE / "attempt_1.json").read_text())
    r_even = run(A.MESSAGES, even_ids, toks, pool, extended=False)
    rec = {n: ref["measurement"]["totals"][n]["main"] for n in names}
    assert r_even["totals"]["main"] == rec, (r_even["totals"]["main"], rec)
    assert all(r_even["rendered"]["main"][m["id"]] == m["encoded"] for m in ref["messages"])
    assert r_even["spec"] == (HERE / "attempt_1_spec.txt").read_text()

    # held-out run
    ids = sorted(MESSAGES)
    assert ids == [f"m{i:02d}" for i in range(1, 40, 2)], ids
    r = run(MESSAGES, ids, toks, pool, extended=True)

    # sanity check 2: every pre-existing entry keeps its frozen form; additions take the next unused pool forms
    for k, f in r_even["forms"].items():
        assert r["forms"][k] == f, (k, f, r["forms"][k])
    assert [e["key"] for e in r["order"][:len(r_even["order"])]] == [e["key"] for e in r_even["order"]]
    pool_forms = [p["form"] for p in pool]
    used = set(r_even["forms"].values())
    additions = []
    for key, gloss, first, why in ADDITIONS:
        f = r["forms"][key]
        pi = pool_forms.index(f)
        lo = next(i for i, p in enumerate(pool_forms) if p not in used)  # next unused form in the frozen ordering
        skipped = [p for p in pool_forms[lo:pi] if p not in used]
        additions.append({"entry": f"{f} = {gloss}", "form": f, "gloss": gloss, "first_used_in": first,
                          "pool_rank": pi, "next_unused_pool_rank": lo,
                          "forms_skipped_by_related_filter": skipped, "why": why,
                          "form_cost": {n: toks[n].count("the " + f) - toks[n].count("the") for n in names}})
        used.add(f)
    used_add = {k for k in r["used_keys"] if k in {a[0] for a in ADDITIONS}}
    assert used_add == {a[0] for a in ADDITIONS}, used_add

    base = {mid: {n: {"en": toks[n].count(corpus[mid]["en"]), "en_terse": toks[n].count(corpus[mid]["en_terse"])}
                  for n in names} for mid in ids}
    totals = {}
    for n in names:
        en = sum(base[m][n]["en"] for m in ids)
        te = sum(base[m][n]["en_terse"] for m in ids)
        mine = r["totals"]["main"][n]
        totals[n] = {"en": en, "en_terse": te, "mine": mine,
                     "mine_vs_en": round(mine / en, 3), "mine_vs_en_terse": round(mine / te, 3),
                     "beats_en_terse": mine < te}
    wins = {n: sum(1 for m in ids if r["per"]["main"][m]["tokens"][n] < base[m][n]["en_terse"]) for n in names}
    ties = {n: sum(1 for m in ids if r["per"]["main"][m]["tokens"][n] == base[m][n]["en_terse"]) for n in names}

    # the same messages with the additions' cost removed (each added form counted as if it cost what the
    # frozen-lexicon paraphrase would) is not computed: no faithful paraphrase was found for them.
    even_totals = {n: {"en": ref["measurement"]["totals"][n]["en"], "en_terse": ref["measurement"]["totals"][n]["en_terse"],
                       "mine": ref["measurement"]["totals"][n]["main"],
                       "mine_vs_en_terse": ref["measurement"]["totals"][n]["main_vs_en_terse"]} for n in names}
    out = {
        "language": "KODEX-1 (attempt 1, codebook strategy), config " + MAIN + ", grammar and lexicon frozen",
        "additions": [a["entry"] for a in additions],
        "paraphrases": PARAPHRASES,
        "messages": [{"id": mid, "encoded": r["rendered"]["main"][mid], "back_translation": MESSAGES[mid][1],
                      "dsl": MESSAGES[mid][0], "en": corpus[mid]["en"], "en_terse": corpus[mid]["en_terse"],
                      "tokens": r["per"]["main"][mid]["tokens"],
                      "en_tokens": {n: base[mid][n]["en"] for n in names},
                      "en_terse_tokens": {n: base[mid][n]["en_terse"] for n in names},
                      "morphemes": r["per"]["main"][mid]["morphemes"],
                      "raw_chunks": r["per"]["main"][mid]["raw_chunks"]} for mid in ids],
        "totals": totals,
        "detail": {
            "additions": additions,
            "per_message_wins_vs_en_terse": wins, "per_message_ties_vs_en_terse": ties,
            "variants_totals": {v: r["totals"][v] for v in ("main", "macros_expanded", "even_spread",
                                                            "RELAXATION_raw_digits")},
            "variants_note": "main = reported 'mine'. macros_expanded = phrase macros replaced by expansions; "
                             "even_spread / RELAXATION_raw_digits as defined in attempt_1.py",
            "morphemes_total": sum(r["per"]["main"][m]["morphemes"] for m in ids),
            "raw_chunks_total": sum(r["per"]["main"][m]["raw_chunks"] for m in ids),
            "spec_tokens_original": r_even["spec_tokens"],
            "spec_tokens_with_additions": r["spec_tokens"],
            "design_set_even_totals_for_reference": even_totals,
            "used_entries": len(r["used_keys"]),
            "used_entries_not_used_on_even_set": sorted(set(r["used_keys"]) - set(r_even["used_keys"])),
            "sanity": "original even run reproduced exactly (totals, rendered messages, spec text); all "
                      "pre-existing forms unchanged",
        },
    }
    (HERE / "heldout_kodex.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))

    print(f"{'':10} " + " ".join(f"{n[:9]:>9}" for n in names))
    for row in ("en", "en_terse", "mine"):
        print(f"{row:10} " + " ".join(f"{totals[n][row]:9}" for n in names))
    print(f"{'mine/te':10} " + " ".join(f"{totals[n]['mine_vs_en_terse']:9.3f}" for n in names))
    print(f"{'mine/en':10} " + " ".join(f"{totals[n]['mine_vs_en']:9.3f}" for n in names))
    print(f"{'even m/te':10} " + " ".join(f"{even_totals[n]['mine_vs_en_terse']:9.3f}" for n in names))
    print("wins/ties vs en_terse:", {n: f"{wins[n]}/{ties[n]}" for n in names})
    print("additions:", [(a["entry"], a["pool_rank"], a["forms_skipped_by_related_filter"]) for a in additions])
    for mid in ids:
        t = r["per"]["main"][mid]["tokens"]
        print(mid, " ".join(f"{t[n]}/{base[mid][n]['en_terse']}" for n in names), "|", r["rendered"]["main"][mid])


if __name__ == "__main__":
    main()
