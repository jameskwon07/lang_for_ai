"""Held-out test of LEAN (lexicon A_conservative): encode the 20 odd-numbered corpus messages (m01..m39), which were
not used to design the grammar or the lexicon, with the FROZEN grammar and lexicon, and measure on 7 tokenizers.

Reuse of the original pipeline:
  - the lexicon is read from a2_lexicon_A_conservative.json (NOT rebuilt: a2_build.lexicon_order sorts the domain block
    with sorted(set(D)), so ties in zipf depend on PYTHONHASHSEED and a rebuild can swap ~68 domain forms; the JSON is
    the frozen artifact that produced a2_results.json, and this script asserts that it reproduces the original
    even-message encodings and totals exactly);
  - encoding uses a2_build.encode, token counting uses toklib (same t.count(text) as a2_build.main);
  - new entries take forms with the a2_build.build loop: the first form in a2_build.form_order() that is not used and
    not excluded by the build's own review rules (MANUAL_SKIP, prefix-of-watched-gloss 'look' set, related()).
    The watch list is the original one (even-message keys + FUNC_GLOSS + ZIPF_ALIAS) plus the content keys of the
    held-out messages, i.e. the same review rule applied to the new test messages (it can only skip forms, never pick a
    cheaper one). With or without the held-out words, and whether the scan starts at the first unused form or after
    the last used one, the result is the same: positions 2501..2506 of the ordering.

Class assignment: content entries of the frozen lexicon whose class is '?' (no even message used them) get the class
needed here (HELD_CLASS); every key keeps one class across all 20 messages, and no class fixed by a2_glosses.CLASS is
changed. 'within' and 'near' are given class P (their natural class; P words are 'listed in the lexicon').

Output: verify/heldout_lean.json
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from toklib import load_all  # noqa: E402
import a2_build as B  # noqa: E402
from a2_glosses import CLASS as EVEN_CLASS, MESSAGES as EVEN_MESSAGES  # noqa: E402

SCENARIO = "A_conservative"

# New entries (no faithful paraphrase with existing entries). Order = first use in the held-out messages.
ADDITIONS = [
    ("exponential", "A", "exponential"),    # m01 exponential backoff (doubling would add a base; no factor/multiply)
    ("calendar", "N", "calendar"),          # m15 calendar quarter (standard/normal do not denote the civil calendar)
    ("loop", "N", "loop"),                  # m25 the loop in merge_records() (no repeat/iteration; cycle is not a loop)
    ("quadratic", "A", "quadratic"),        # m25 (grow+square paraphrase reads as a past event; EQ square = equality)
    ("encyclopedia", "N", "encyclopedia"),  # m33 (reference book is a hypernym and loses the source type)
    ("euro", "N", "euro"),                  # m39 850 euros (money/dollar lose the currency)
]

# Classes for frozen '?' entries used in the held-out messages (one class per key).
HELD_CLASS = {
    # V
    "refactor": "V1", "retry": "V1", "use": "V1", "turn": "V1", "process": "V1", "finish": "V0", "wait": "V0",
    "combine": "V1", "list": "V1", "remove": "V1", "confirm": "VC", "depend": "V0", "target": "V1", "mean": "V1",
    "fail": "V0", "stop": "V1", "avoid": "V1", "translate": "V1", "continue": "V0", "propose": "V1",
    "collect": "V1", "group": "V1", "sort": "V1", "want": "V1", "start": "V1", "oppose": "V1", "expect": "V1",
    "consider": "V1", "cut": "V1", "bring": "V1", "drop": "V1", "come": "V0", "flag": "V1", "verify": "V1",
    "commit": "V1", "book": "V1", "travel": "V0", "stay": "V0",
    # A
    "maximum": "A", "public": "A", "current": "A", "successful": "A", "local": "A", "official": "A", "total": "A",
    "small": "A", "technical": "A", "last": "A", "financial": "A", "negative": "A", "hard": "A", "slow": "A",
    "easy": "A", "whole": "A", "good": "A", "long": "A", "cheap": "A", "large": "A", "real": "A",
    "unreliable": "A",
    # D
    "approximately": "D", "instead": "D", "overall": "D", "slightly": "D",
    # P
    "within": "P", "near": "P",
    # N
    "code": "N", "backoff": "N", "attempt": "N", "interface": "N", "question": "N", "query": "N", "sale": "N",
    "database": "N", "record": "N", "rate": "N", "job": "N", "minute": "N", "unit": "N", "machine": "N",
    "pull": "N", "changelog": "N", "module": "N", "tool": "N", "cost": "N", "detail": "N", "level": "N",
    "audience": "N", "executive": "N", "engineer": "N", "quarter": "N", "payment": "N", "api": "N",
    "series": "N", "input": "N", "customer": "N", "feedback": "N", "theme": "N", "count": "N", "reviewer": "N",
    "cache": "N", "front": "N", "risk": "N", "rollback": "N", "patch": "N", "row": "N", "map": "N", "key": "N",
    "plan": "N", "model": "N", "case": "N", "outlier": "N", "device": "N", "fault": "N", "capital": "N",
    "government": "N", "web": "N", "site": "N", "bug": "N", "handoff": "N", "branch": "N", "state": "N",
    "flight": "N", "person": "N", "hotel": "N", "town": "N",
}

R = "RAW"
MESSAGES = [
    ("m01", ["IMP", "refactor", "retry", "LK", "code", "IN", "QT", (R, "src/net/client.py"), "use", "exponential",
             "backoff", "WITH", "maximum", "d5", "attempt", "NEG", "change", "public", "interface"],
     "[request mode] Refactor the code of retrying (retry logic) in src/net/client.py; use exponential backoff with a "
     "maximum of five attempts; do not change the public interface."),
    ("m03", ["IMP", "turn", "user", "question", "TO", "QT", (R, "SQL"), "query", "ON", "sale", "database", "run", "IT",
             "return", "ONLY", "result", "NEG", "return", "query"],
     "[request mode] Turn the user question into an SQL query on the sales database; run it; return only the result; "
     "do not return the query."),
    ("m05", ["process", "d1", "THOUSAND", "d2", "HUNDRED", "FROM", "d3", "THOUSAND", "record", "SOFAR", "job", "MUST",
             "finish", "IN", "d20", "d5", "minute", "approximately", "AT", "current", "rate"],
     "I have processed 1200 from (out of) 3000 records so far. The job should finish in 25 minutes, approximately, at "
     "the current rate."),
    ("m07", ["EVERY", "unit", "LK", "test", "successful", "ON", "local", "machine", "PROG", "wait", "FOR", "combine",
             "part", "LK", "test", "LK", "finish", "THEN", "FUT", "open", "pull", "request"],
     "Every unit test (test of every unit) is successful on the local machine. I am waiting for the finishing of the "
     "tests of the combined parts (integration tests); then I will open the pull request."),
    ("m09", ["d10", "d4", "result", "FROM", "search", "MOST", "relevant", "EQ", "official", "changelog", "AT", "QT",
             (R, "https://docs.python.org/3/whatsnew/3.13.html"), "REL", "list", "remove", "module"],
     "There are 14 results from the search. The most relevant one is the official changelog, at "
     "https://docs.python.org/3/whatsnew/3.13.html, which lists the removed modules."),
    ("m11", ["calculation", "tool", "confirm", "budget", "cover", "total", "cost", "BUT", "budget", "LK", "rest",
             "small"],
     "The calculation tool (calculator) confirmed that the budget covers the total cost, but the rest of the budget "
     "(remaining margin) is small."),
    ("m13", ["technical", "detail", "LK", "level", "depend", "ON", "audience", "Q", "summary", "MUST", "target",
             "executive", "OR", "IT", "MUST", "target", "engineer"],
     "The level of technical detail depends on the audience. [question mode] Should the summary target executives, or "
     "should it target engineers?"),
    ("m15", ["ABOUT", "last", "quarter", "Q", "YOU", "mean", "MOST", "recent", "calendar", "quarter", "OR", "YOU",
             "mean", "company", "LK", "financial", "quarter"],
     "[frame:] About 'last quarter': [question mode] do you mean the most recent calendar quarter, or do you mean the "
     "company's financial (fiscal) quarter?"),
    ("m17", ["payment", "api", "request", "fail", "WITH", "QT", (R, "HTTP 503"), "ON", "d3", "attempt", "IN",
             "series", "stop", "retry", "FOR", "rate", "LK", "limit", "LK", "avoid"],
     "The payment-API request failed with HTTP 503 on three attempts in series (in a row). I stopped retrying, for "
     "the avoidance of the rate limit."),
    ("m19", ["fail", "IN", "translate", "LK", "step", "BECAUSE", "input", "MORE", "long", "THAN", "context", "LK",
             "limit", "CAN", "split", "document", "IN", "part", "ET", "CAN", "retry", "DELIB", "continue"],
     "I failed in the step of translating (the translation step failed) because the input is longer than the context "
     "limit. I can split the document into parts and can retry. [should-I mode] Should I continue (go ahead)?"),
    ("m21", ["propose", "d3", "step", "HORT", "collect", "negative", "customer", "feedback", "group", "FROM", "theme",
             "sort", "theme", "FROM", "count", "DECL", "MOST", "hard", "step", "EQ", "group", "SO", "want", "second",
             "reviewer", "FOR", "IT", "FUT", "start", "collect", "IF", "YOU", "NEG", "oppose", "IMP", "expect",
             "first", "result", "within", "d1", "hour"],
     "I propose three steps. [let's] Collect negative customer feedback (complaints), group [it] based on theme, sort "
     "the themes based on count (frequency). [statement] The hardest step is grouping, so I want a second reviewer for "
     "it. I will start collecting if you do not oppose. [request] Expect the first results within one hour."),
    ("m23", ["WE", "CAN", "add", "cache", "IN", "slow", "query", "LK", "front", "instead", "THAT", "EQ", "easy",
             "rollback", "ET", "MORE", "low", "risk", "THAN", "whole", "module", "PASS", "write", "again"],
     "We could add a cache in front of the slow queries instead. That (plan) is an easy rollback and lower risk than "
     "the whole module being written again (rewriting the whole module)."),
    ("m25", ["patch", "correct", "BUT", "QT", (R, "merge_records()"), "LK", "loop", "quadratic", "IT", "FUT", "TOO",
             "slow", "WITH", "d1", "HUNDRED", "THOUSAND", "row", "SO", "IMP", "consider", "QT", (R, "ID"), "key",
             "map"],
     "The patch is correct, but the loop of merge_records() is quadratic. It will be too slow with 100,000 rows, so "
     "[request] consider an ID-key map (a dictionary keyed by ID)."),
    ("m27", ["summary", "good", "overall", "IT", "TOO", "long", "slightly", "background", "part", "LK", "cut", "FUT",
             "bring", "IT", "within", "limit"],
     "The summary is good overall. It is too long, slightly. Cutting the background part will bring it within the "
     "limit."),
    ("m29", ["agree", "YOUR", "plan", "WITH", "d1", "change", "IMP", "run", "MORE", "cheap", "model", "FIRSTLY", "use",
             "MORE", "large", "FOR", "ONLY", "hard", "case"],
     "I agree with your plan, with one change: [request] run the cheaper model first; use the larger one for only "
     "the hard cases."),
    ("m31", ["NEG", "agree", "outlier", "LK", "drop", "THEY", "come", "FROM", "real", "measurement", "device", "fault",
             "SO", "WE", "MUST", "flag", "instead"],
     "I do not agree with dropping the outliers. They come from a real measurement-device (sensor) fault, so we should "
     "flag [them] instead [of dropping/deleting them]."),
    ("m33", ["QT", (R, "Australia"), "capital", "EQ", "QT", (R, "Canberra"), "ET", "NEG", "EQ", "QT", (R, "Sydney"),
             "PD", "confidence", "high", "source", "EQ", "QT", (R, "Australian"), "government", "web", "site", "ET",
             "d2", "encyclopedia"],
     "The Australia capital is Canberra and is not Sydney. Confidence is high. The sources are the Australian "
     "government web site and two encyclopedias."),
    ("m35", ["QT", (R, "https://github.com/example-org/tilemap/blob/main/CHANGELOG.md"), "changelog", "confirm", "bug",
             "PASS", "fix", "IN", "d4", "POINT", "d2", "POINT", "d1", "I", "verify", "fix", "ON", "local", "machine",
             "PD", "confidence", "high"],
     "The https://github.com/example-org/tilemap/blob/main/CHANGELOG.md changelog confirmed that the bug was fixed in "
     "4.2.1. I verified the fix on the local machine. Confidence is high."),
    ("m37", ["FOR", "handoff", "commit", "fix", "TO", "QT", (R, "fix/login-timeout"), "branch", "PD", "rest", "EQ", "QT",
             (R, "test_auth.py"), "LK", "update", "unreliable", "test", "EQ", "QT", (R, "test_session_expiry"), "REL",
             "fail", "IN", "d1", "FROM", "d10", "run", "approximately"],
     "[frame:] For handoff: I committed the fix to the fix/login-timeout branch. The rest is updating test_auth.py. "
     "The unreliable (flaky) test is test_session_expiry, which fails in one from (out of) ten runs, approximately."),
    ("m39", ["state", "SOFAR", "QT", (R, "Lisbon"), "flight", "PASS", "book", "FOR", "d2", "travel", "person", "BUT",
             "hotel", "NEG", "PASS", "book", "budget", "LK", "rest", "EQ", "d8", "HUNDRED", "d50", "euro", "PD",
             "user", "want", "stay", "near", "old", "town"],
     "State so far: the Lisbon flights were booked for the two travelling persons (both travelers), but the hotel was "
     "not booked. The rest of the budget is 850 euros. The user wants a stay near the old town."),
]

PARAPHRASES = [
    "m01 'retry logic' -> 'retry LK code' (code of retrying); no entry 'logic'",
    "m01 'keep the public interface unchanged' -> 'NEG change public interface'; no entry 'unchanged'",
    "m01 'at most 5 attempts' -> 'maximum d5 attempt'",
    "m03 'report (verb)' -> 'return' (entry 'report' is fixed as N by the even glosses)",
    "m03 'sales database' -> 'sale database' (no plural; 'sales' is not an entry)",
    "m05 '1,200 of 3,000 records' -> 'd1 THOUSAND d2 HUNDRED FROM d3 THOUSAND record' (partitive 'of'; LK is possessive)",
    "m05/m37 'about N' (approximately) -> D 'approximately' (ABOUT is the topic preposition)",
    "m07 'pass' -> 'successful'; no entry 'pass'",
    "m07/m35 'locally' -> 'ON local machine'; no entry 'locally'",
    "m07 'unit tests' -> 'EVERY unit LK test' (test of every unit): 'test' is fixed V1 and a V cannot head an N compound",
    "m07 'integration tests' -> 'combine part LK test' (test of combined parts); no entry 'integration'",
    "m07 'pull request' -> 'pull request' with 'pull' given class N",
    "m09 'The search returned 14 results' -> 'd10 d4 result FROM search' (14 results from the search): 'search' is V1 and "
    "cannot start a subject; 'return' is V2 and would take the next clause's NP as second object",
    "m09 'removed modules' -> 'remove module' (participle)",
    "m11 'calculator' -> 'calculation tool'; no entry 'calculator'",
    "m11 'total cost is within budget' -> 'budget cover total cost'",
    "m11 'remaining margin' -> 'budget LK rest' (rest of the budget); no entry 'margin'/'remaining'",
    "m13 alternative question -> 'Q ... OR IT MUST target ...' (OR links clauses only); sentence order swapped",
    "m15 'fiscal' -> 'financial'; no entry 'fiscal'",
    "m15 'By 'last quarter'' -> frame 'ABOUT last quarter'",
    "m17 'payments API' -> 'payment api'",
    "m17 'three times in a row' -> 'ON d3 attempt IN series'; no entry 'consecutive'",
    "m17 'rate limit' -> 'rate LK limit' (limit is fixed V1, so 'rate limit' would parse as subject + verb)",
    "m17 'to avoid hitting the rate limit' -> 'FOR rate LK limit LK avoid' (for avoidance of the rate limit)",
    "m19 'the translation step failed' -> 'fail IN translate LK step' (I failed in the translation step); no entry "
    "'translation', and a V at clause start is the predicate",
    "m19 'exceeded' -> 'MORE long THAN'; no entry 'exceed'",
    "m19 'chunks' -> 'part'; no entry 'chunk'",
    "m19 'Should I go ahead?' -> 'DELIB continue'; no entry 'proceed'",
    "m21 'customer complaints' -> 'negative customer feedback'; no entry 'complaint'",
    "m21 'rank' -> 'sort'; no entry 'rank'",
    "m21 'by frequency' -> 'FROM count'; no entry 'frequency' (BY is glossed 'by (agent)', so criterion 'by' -> FROM)",
    "m21 'there' -> 'FOR IT'; no entry 'there'",
    "m21 'unless you object' -> 'IF YOU NEG oppose'; 'unless' is a frozen '?' entry but CONJ is a closed list in the "
    "grammar text",
    "m21 'would like' -> 'want'",
    "m23 'caching layer' -> 'cache'; no entry 'layer'",
    "m23 'rewriting' -> 'PASS write again'; no entry 'rewrite'",
    "m23 'Instead of rewriting the whole module, we could ...' -> 'WE CAN ... instead' + 'THAN whole module PASS write "
    "again' in the next sentence",
    "m23 'easy to revert' -> 'easy rollback'; no entry 'revert'",
    "m23 'in front of X' -> 'IN X LK front'",
    "m25 'dictionary keyed by ID' -> 'QT ID key map'; no entry 'dictionary'/'dict'",
    "m27 'paragraph' -> 'part'; no entry 'paragraph'",
    "m29 'cheaper'/'larger' -> 'MORE cheap'/'MORE large'",
    "m31 'disagree' -> 'NEG agree'; no entry 'disagree'",
    "m31 'sensor' -> 'measurement device'; no entry 'sensor'",
    "m31 'instead of deleting them' -> 'instead' (the deleting = the dropping named in the first clause)",
    "m33 'website' -> 'web site'; no entry 'website'",
    "m35 'Yes,' -> dropped; the affirmative answer is the following clause (no entry 'yes')",
    "m35 'reproduced the fix' -> 'verify fix'; no entry 'reproduce'",
    "m35 'version 4.2.1' -> 'd4 POINT d2 POINT d1' (a number right before 'version' would be a quantity)",
    "m35 'The changelog at URL confirms it' -> 'QT URL changelog confirm [bug PASS fix ...]' (NP cannot contain P)",
    "m37 'Handing off:' -> frame 'FOR handoff'",
    "m37 'the fix is on branch X' -> 'commit fix TO QT X branch' (makes the agent 'I' explicit; 'fix' is V1 and "
    "cannot start a subject)",
    "m37 'remaining work' -> 'rest'",
    "m37 'flaky' -> 'unreliable'; no entry 'flaky'",
    "m37 'one run in ten' -> 'IN d1 FROM d10 run'",
    "m39 'travelers' -> 'travel person' (V0 participle); no entry 'traveler'",
    "m39 'both' -> 'd2'; no entry 'both'",
    "m39 'remaining budget' -> 'budget LK rest'",
]

NOTES_DROPPED = [
    "m01 'Please' not encoded: IMP is the request mode ('please' is a frozen entry, form 'delet', not used)",
    "m35 'Yes' not encoded (see paraphrases)",
]
GRAMMAR_STRETCH = [
    "m33 'QT Sydney PD confidence': PD is defined for N+N; here a raw span would otherwise modify the next N",
    "m25 'SO IMP consider ...': a mode word placed right after a CONJ",
    "m17 'QT HTTP 503': status code written as a raw identifier span (digits included verbatim)",
]


def addition_forms(lex, held_keys):
    """Continue the a2_build.build form-assignment loop for the new entries."""
    forms = B.form_order()
    watch = sorted({t for _, seq, _ in EVEN_MESSAGES for t in seq if isinstance(t, str) and t[:1].islower()}
                   | set(held_keys))
    watch = [w.replace(" ", "") for w in watch] + B.FUNC_GLOSS + list(B.ZIPF_ALIAS.values())
    look = {f["form"] for f in forms if len(f["form"]) >= 4 and any(g.startswith(f["form"]) and g != f["form"]
                                                                    for g in watch)}
    used = {e["form"] for e in lex.values()}
    pos = {f["form"]: i for i, f in enumerate(forms)}
    out = {}
    idx = len(lex)
    for key, cls, gloss in ADDITIONS:
        j = 0
        while (forms[j]["form"] in used or forms[j]["form"] in B.MANUAL_SKIP or forms[j]["form"] in look
               or B.related(forms[j]["form"], gloss)):
            j += 1
        f = forms[j]
        used.add(f["form"])
        out[key] = {"form": f["form"], "class": cls, "gloss": gloss, "index": idx, "costs": f["costs"],
                    "form_order_position": j, "last_frozen_position": max(pos[e["form"]] for e in lex.values())}
        idx += 1
    return out, look


def main():
    toks = load_all()
    names = list(toks)
    corpus = {m["id"]: m for m in json.loads((HERE.parent / "corpus" / "ai_messages.json").read_text())}
    lex = json.loads((HERE / f"a2_lexicon_{SCENARIO}.json").read_text())
    orig = json.loads((HERE / "a2_results.json").read_text())

    # 1. the frozen lexicon + encoder reproduce the original even-message run exactly
    enc_even = {mid: B.encode(lex, seq) for mid, seq, _ in EVEN_MESSAGES}
    assert enc_even == orig["scenarios"][SCENARIO]["encoded"], "frozen lexicon does not reproduce a2_results.json"
    tot_even = {n: sum(t.count(s) for s in enc_even.values()) for n, t in toks.items()}
    assert tot_even == orig["scenarios"][SCENARIO]["total"]

    # 2. held-out ids = the 20 odd messages
    ids = [mid for mid, _, _ in MESSAGES]
    assert ids == [f"m{i:02d}" for i in range(1, 40, 2)], ids

    # 3. classes: one per key, no change to classes fixed by the even glosses or the function block
    used_keys = [t for _, seq, _ in MESSAGES for t in seq if isinstance(t, str)]
    add_keys = {k for k, _, _ in ADDITIONS}
    for k in set(used_keys):
        if k in add_keys:
            assert k not in lex, f"addition already in lexicon: {k}"
            continue
        assert k in lex, f"not in lexicon and not an addition: {k}"
        frozen_cls = lex[k]["class"]
        if frozen_cls != "?":
            assert k not in HELD_CLASS, f"{k} already has class {frozen_cls}"
        else:
            assert k in HELD_CLASS, f"no class assigned for '?' entry {k}"
            assert k not in EVEN_CLASS
    assert not set(HELD_CLASS) - set(used_keys), set(HELD_CLASS) - set(used_keys)

    # 4. forms for the additions (continuation of the build loop)
    add, look = addition_forms(lex, [k for k in set(used_keys) if k[:1].islower()])
    full = dict(lex)
    full.update(add)

    # 5. encode and count
    enc = {mid: B.encode(full, seq) for mid, seq, _ in MESSAGES}
    per = {mid: {n: t.count(s) for n, t in toks.items()} for mid, s in enc.items()}
    tot = {n: sum(per[m][n] for m in ids) for n in names}
    base = {k: {n: sum(t.count(corpus[i][k]) for i in ids) for n, t in toks.items()} for k in ["en", "en_terse"]}
    base_per = {k: {i: {n: t.count(corpus[i][k]) for n, t in toks.items()} for i in ids} for k in ["en", "en_terse"]}
    totals = {n: {"en": base["en"][n], "en_terse": base["en_terse"][n], "mine": tot[n]} for n in names}
    ratio_en = {n: round(tot[n] / base["en"][n], 3) for n in names}
    ratio_terse = {n: round(tot[n] / base["en_terse"][n], 3) for n in names}
    wins_terse = {n: sum(1 for i in ids if per[i][n] < base_per["en_terse"][i][n]) for n in names}
    wins_en = {n: sum(1 for i in ids if per[i][n] < base_per["en"][i][n]) for n in names}

    # tokens attributable to the additions (per tokenizer, counted as in-context forms)
    add_uses = {k: used_keys.count(k) for k in add_keys}
    add_cost = {n: sum(add[k]["costs"][n] * add_uses[k] for k in add_keys) for n in names}

    # raw spans: tokens of the encodings with every raw span removed (QT kept) vs total
    n_morph = sum(1 for t in used_keys)
    n_raw = sum(1 for _, seq, _ in MESSAGES for t in seq if isinstance(t, tuple))

    # diagnostic: forms used here that the build's review rule would have blocked had these messages been the test set
    # (4+ letters, proper prefix of a held-out content gloss, a function-word gloss, or an alias)
    held_watch = [k.replace(" ", "") for k in set(used_keys) if k[:1].islower()] + B.FUNC_GLOSS
    confusable = sorted({(k, full[k]["form"], g) for k in set(used_keys) for g in held_watch
                         if len(full[k]["form"]) >= 4 and g.startswith(full[k]["form"]) and g != full[k]["form"]})

    even = orig["scenarios"][SCENARIO]
    res = {
        "scenario": SCENARIO,
        "additions": [f"{k} = {add[k]['gloss']} (class {add[k]['class']}, form '{add[k]['form']}', form-order "
                      f"position {add[k]['form_order_position']}, cost over 7 tokenizers "
                      f"{sum(add[k]['costs'].values())}, uses {add_uses[k]})" for k, _, _ in ADDITIONS],
        "paraphrases": PARAPHRASES,
        "messages": [{"id": mid, "encoded": enc[mid], "back_translation": bt, "en": corpus[mid]["en"],
                      "en_terse": corpus[mid]["en_terse"], "tokens": per[mid],
                      "tokens_en": base_per["en"][mid], "tokens_en_terse": base_per["en_terse"][mid]}
                     for mid, _, bt in MESSAGES],
        "totals": totals,
        "ratio_vs_en": ratio_en,
        "ratio_vs_en_terse": ratio_terse,
        "beats_en_terse_total_on": [n for n in names if tot[n] < base["en_terse"][n]],
        "msgs_shorter_than_en_terse": wins_terse,
        "msgs_shorter_than_en": wins_en,
        "addition_tokens_in_total": add_cost,
        "n_morphemes_excl_raw": n_morph,
        "n_raw_spans": n_raw,
        "addition_entries": add,
        "class_assignments_for_frozen_unknown_class_entries": HELD_CLASS,
        "dropped": NOTES_DROPPED,
        "grammar_stretches": GRAMMAR_STRETCH,
        "confusable_forms_in_heldout": [f"{k}: form '{f}' is a prefix of '{g}'" for k, f, g in confusable],
        "reference_even_design_set": {
            "totals": {n: {"en": orig["baseline"]["en"][n], "en_terse": orig["baseline"]["en_terse"][n],
                           "mine": even["total"][n]} for n in names},
            "ratio_vs_en": even["ratio_vs_en"], "ratio_vs_en_terse": even["ratio_vs_en_terse"],
            "n_morphemes_excl_raw": even["n_morphemes_excl_raw"],
        },
        "check_even_reproduced": True,
    }
    (HERE / "heldout_lean.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))

    print("additions:", [(k, add[k]["form"], add[k]["form_order_position"], sum(add[k]["costs"].values()))
                         for k, _, _ in ADDITIONS])
    print(f"{'tokenizer':15s} {'en':>5s} {'terse':>6s} {'mine':>5s} {'/en':>6s} {'/terse':>7s} {'wins/terse':>10s}")
    for n in names:
        print(f"{n:15s} {base['en'][n]:5d} {base['en_terse'][n]:6d} {tot[n]:5d} {ratio_en[n]:6.3f} "
              f"{ratio_terse[n]:7.3f} {wins_terse[n]:10d}")
    print("even reference ratio vs en_terse:", even["ratio_vs_en_terse"])
    print("addition tokens in total:", add_cost)
    print("morphemes(excl raw):", n_morph, "raw spans:", n_raw)
    print("confusable:", len(confusable))
    for mid in ids:
        print(mid, per[mid]["o200k"], base_per["en_terse"][mid]["o200k"], "|", enc[mid])


if __name__ == "__main__":
    main()
