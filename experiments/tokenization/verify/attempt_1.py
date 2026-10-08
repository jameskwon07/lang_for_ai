"""Attempt 1 (advocate, codebook / macro-morpheme strategy): encode m02, m04, ..., m40 and measure.

Run from experiments/tokenization:  python3 verify/attempt_1.py
Writes verify/attempt_1.json (required format + measurements), verify/attempt_1_spec.txt (the full spec text,
used only to count its tokens) and prints a summary.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from toklib import load_all  # noqa: E402
from forms_attempt_1 import load_pool  # noqa: E402
from lexicon_attempt_1 import build_entries, priority_order, MACROS  # noqa: E402

# ---------------------------------------------------------------- the 20 messages
# DSL: _X grammar, @x macro, #n number (digits, optional decimal point), "raw text" quoted raw chunk(s), word = root.
MESSAGES = {
    "m02": ('find recent peer_reviewed study _ON _HOW sleep lack affect work memory _SEP '
            '@return_top #5 @one_sentence_summary _EACH',
            "Find recent peer-reviewed studies on how sleep deprivation (lack of sleep) affects working memory. "
            "Return the 5 most relevant, with a one-sentence summary each."),
    "m04": ('draft polite reply _CNT decline meet request suggest #2 alternative time @later_this_week',
            "Draft a polite reply: (it) declines the meeting request and proposes 2 alternative times later this week."),
    "m06": ('@lit_search _DONE _PROG read shortlist paper @no_blockers',
            "The literature search is done; I am now reading the shortlisted papers. No blockers so far."),
    "m08": ('_FIRST report draft _DONE _CNT background _AND method _AND result _SEP discussion _STILL miss',
            "The first report draft is done: (it covers) background, methods and results. "
            "The discussion is still missing."),
    "m10": ('file scan _CNT _NO duplicate _SEP #3 column _WITH miss value mostly _IN address field',
            "File scan: no duplicates. 3 columns have missing values, mostly in the address field."),
    "m12": ('"Maria Lopez" own billing service _SEP "Kenji Sato" _IS backup on_call @per company directory',
            "Maria Lopez owns the billing service; Kenji Sato is the backup on-call (engineer). "
            "(All according to the company directory.)"),
    "m14": ('_SHOULD change "parse_config()" direct _OR add new function keep old @for_backcompat _QUES',
            "Should I change (modify) parse_config() directly, or add a new function and keep the old one "
            "for backward compatibility?"),
    "m16": ('#2 source document give different deadline _WHICH authoritative',
            "The 2 source documents give different deadlines. Which (one) is authoritative?"),
    "m18": ('_FAIL open "data/2024/q3_sales.csv" _CAUSE @not_found _PASS move _TO _OTHER folder _QUES',
            "I could not open data/2024/q3_sales.csv because it does not exist. Was it moved to another folder?"),
    "m20": ('@my_prev_answer wrong _CAUSE _PAST confuse #2 dataset _SEP figure _PASS correct _IN update table',
            "My previous answer was wrong because I mixed up (confused) the 2 datasets. "
            "The figures are corrected in the updated table."),
    "m22": ('@in_order upgrade numpy _TO #2.1 fix deprecation warn raise minimum python _TO #3.11',
            "Proposed plan, strictly in this order: upgrade numpy to 2.1, fix the deprecation warnings, "
            "raise the minimum Python (version) to 3.11."),
    "m24": ('_HORT split work _CNT _I handle data clean _YOU handle visualization _WE merge result final '
            '_HORT agree column name _FIRST @does_that_work',
            "Let's split the work: I handle data cleaning, you handle the visualizations, we merge the results "
            "at the end (finally). Let's agree on column names first. Does that work for you?"),
    "m26": ('argument persuasive _BUT _NO cite source support claim #2 _SEP add source _OR hedge claim',
            "The argument is persuasive, but none of the cited sources supports claim 2 (the second claim). "
            "Add a source or soften (hedge) the claim."),
    "m28": ('_PAST check _YOUR calculation _CNT step #3 error _CNT tax _PASS apply twice _CONSE final amount '
            '_SHOULD lower @rest_correct',
            "I checked your calculation: (there is an) error in step 3: the tax was applied twice, so the final "
            "amount should be lower. Everything else is correct."),
    "m30": ('_CAN take frontend task _BUT need #2 _MORE day _THAN _YOU suggest _IF _TOO late _CAN deliver '
            'partial version _BY original date',
            "I can take the frontend tasks, but I need 2 more days than you proposed (suggest). If (that is) too "
            "late, I can deliver a partial version by the original date."),
    "m32": ('_YOUR #40 @gpu_hour estimate seem high _MY measure suggest #25 enough _HORT compromise _AT #30 '
            'review _AGAIN _AFTER _FIRST run _QUES',
            "Your 40 GPU-hour estimate seems high. My measurement suggests 25 is enough. Shall/can we compromise "
            "at 30 and review (revisit) it again after the first run?"),
    "m34": ('slowdown @likely_cause _CNT new log config write _EVERY request _TO disk @conf_fair_tool profiler '
            '_NOTYET test fix',
            "Most likely cause of the slowdown: the new logging config(uration), (which) writes every request to "
            "disk. I am fairly confident, based on the profiler's output. I have not yet tested a fix."),
    "m36": ('_FAIL find reliable answer _SEP #2 find source conflict _SEP _MORE new support option #2 @conf_low',
            "I could not find a reliable answer. The 2 sources I found conflict (contradict each other); the newer "
            "one supports option 2 (the second option). My confidence is low."),
    "m38": ('@context_next_agent user prefer short answer _THEY _ALREADY reject _FIRST #2 design _THEY _PAST like '
            'design #3 color scheme _BUT _NEG layout _SEP budget _PASS fix _CONSE _DONT ask _AGAIN',
            "Context for the next agent: the user prefers short answers. They have already rejected the first 2 "
            "designs. They liked design 3's color scheme but not (its) layout. The budget is fixed, so do not ask "
            "(about it) again."),
    "m40": ('@pass_back task _CAUSE @needs_human_approval _ALL ready _SEP _ONLY final confirmation miss',
            "I am passing this task back to you because it needs human approval. Everything is ready (prepared); "
            "only the final confirmation is missing."),
}

GRAMMAR_TEXT = """KODEX-1 spec. AI-to-AI language. A message = lexicon forms separated by single spaces; each form is one
entry below (case is part of the form). No punctuation.
RAW: Q1, Q2, Q3 = the next 1, 2, 3 space-separated chunks are raw text copied verbatim (paths, code, names, URLs).
NUMBERS: digit forms 0..9 (table). Consecutive number forms are one number: concatenate their digits
(4 0 = 40; 2 0 2 4 = 2024). POINT = decimal point (3 POINT 1 1 = 3.11). A number before a noun is a
count (3 column = 3 columns); a number right after a noun is a label (claim 2 = claim #2 = the second claim).
ORD n = n-th; n TIMES = n times.
CLASSES: roots are nouns, verbs or modifiers as in English (one root covers noun/verb/adjective/adverb uses);
G = grammar; P = codebook phrase (S = whole clause, NP, VP, M = modifier/adverbial).
NOUN PHRASE: [quantifier|number] [modifier]* [noun]* head. Earlier nouns modify the last (billing service). Plural is
unmarked. A verb root before the head is its past participle when that reading fits (cite source = cited sources;
update table = updated table); a verb root as head is the action (data clean = data cleaning). A modifier alone can
be the head (MORE new = the newer one). Lists: AND / OR between items.
CLAUSE: [subject] [TAM]* predicate [object] [complements] [adverbs]. Predicate = verb, or modifier (copula omitted:
answer wrong = the answer is wrong), or IS + NP. Prepositions precede their NP. A modifier after the verb phrase is an
adverb (change X direct = change X directly). A verb after a complete verb phrase starts a second verb phrase with
the same subject (decline X propose Y).
OMITTED SUBJECT: verb-first clause without TAM = imperative to the addressee; clause opened by a TAM (PAST PROG FUT
DONE ALREADY NOTYET CAN FAIL SHOULD MUST MAY) = speaker (I); HORT = we (let us / I propose we); after a connective
(BUT CAUSE CONSE IF THEN OR) = same subject as the previous clause; PASS without subject = the last-mentioned thing.
CLAUSE BOUNDARIES: SEP ends a clause. A new clause starts without SEP at: a connective; a TAM, HORT or DONT when the
current clause already has its predicate; a pronoun subject (I YOU WE THEY IT, or MY/YOUR + NP) after a complete
clause; a wh-word; a clause phrase (P:S). Otherwise write SEP. CNT = ':' (elaboration: namely / consisting of /
which is / with content). IF A B: A = condition, B = consequence.
QUESTIONS: QUES at clause end = yes/no question. A clause opened by a wh-word is a question (no QUES).
HORT ... QUES = shall we / can we ...?
PRAGMATICS: unmarked = plain assertion, normal confidence. CONF phrases state the speaker's confidence in the
preceding clause(s); a following NP names the tool or source. PER NP = according to NP; at message end it covers
the whole message.
LEXICON (form gloss). G and numbers first, then phrases (P), then roots by frequency."""


def related(form: str, gloss: str) -> bool:
    """True if the form looks like a fragment of a word in its own gloss (would leak meaning)."""
    f = form.lower()
    for w in re.findall(r"[a-z]+", gloss.lower()):
        if len(w) < 3:
            continue
        k = min(4, len(f), len(w))
        if k >= 3 and f[:k] == w[:k]:
            return True
        if len(f) >= 4 and f in w:
            return True
        if len(w) >= 4 and w in f:
            return True
    return False


# meaning-specific leaks found by manual review (form would hint at this entry's meaning): skip for that entry only
VETO = {("summar", "report"), ("relinqu", "compromise"), ("errone", "wrong"), ("errone", "error"),
        ("amist", "polite"), ("komment", "discussion"), ("perc", "figure"), ("strate", "@in_order"),
        ("axi", "visualization"), ("preci", "@one_sentence_summary"), ("perc", "value"), ("incom", "budget"),
        ("opc", "function"), ("aussch", "deprecation"), ("zeich", "layout")}


def assign_forms(order: list[dict], pool: list[dict]) -> dict[str, str]:
    used: set[int] = set()
    out: dict[str, str] = {}
    i = 0
    for e in order:
        j = i
        while j in used or related(pool[j]["form"], e["gloss"] + " " + e["key"]) or (pool[j]["form"], e["key"]) in VETO:
            j += 1
        used.add(j)
        out[e["key"]] = pool[j]["form"]
        while i in used:
            i += 1
    return out


def dsl_tokens(dsl: str) -> list[str]:
    return re.findall(r'"[^"]*"|\S+', dsl)


N_NUM = 100  # set by main(); 10 = one form per digit, 100 = forms for 0..99


def number_keys(numstr: str) -> list[str]:
    """digits -> number-form keys: greedy 2-digit chunks that do not start with 0 (decimal part the same way)."""
    def chunk(d: str) -> list[str]:
        out, i = [], 0
        while i < len(d):
            if N_NUM == 100 and d[i] != "0" and i + 1 < len(d):
                out.append("#" + str(int(d[i:i + 2])))
                i += 2
            else:
                out.append("#" + d[i])
                i += 1
        return out
    if "." in numstr:
        a, b = numstr.split(".")
        return chunk(a) + ["_POINT"] + chunk(b)
    return chunk(numstr)


def expand(dsl_toks: list[str], expand_macros: bool, macro_exp: dict[str, str],
           raw_digits: bool = False) -> list[tuple[str, str]]:
    """-> list of (kind, value): ('key', entry key) or ('raw', text). raw_digits = RELAXATION: numbers as digits."""
    out: list[tuple[str, str]] = []
    for t in dsl_toks:
        if t.startswith("#") and raw_digits:
            out.append(("raw", t[1:]))
            continue
        if t.startswith('"'):
            raw = t.strip('"')
            n = len(raw.split(" "))
            out.append(("key", f"_Q{n}"))
            out.append(("raw", raw))
        elif t.startswith("#"):
            out += [("key", k) for k in number_keys(t[1:])]
        elif t.startswith("@") and expand_macros:
            out += expand(dsl_tokens(macro_exp[t]), False, macro_exp)
        else:
            out.append(("key", t))
    return out


def render(seq: list[tuple[str, str]], forms: dict[str, str]) -> str:
    return " ".join(forms[v] if k == "key" else v for k, v in seq)


def spec_text(order: list[dict], forms: dict[str, str]) -> str:
    """Full spec: grammar text + lexicon. Roots are written as 'form meaning' pairs, 16 per line (compact)."""
    g = GRAMMAR_TEXT
    if N_NUM == 100:
        g = g.replace("digit forms 0..9 (table). Consecutive number forms are one number: concatenate their digits\n"
                      "(4 0 = 40; 2 0 2 4 = 2024). POINT = decimal point (3 POINT 1 1 = 3.11).",
                      "number forms 0..99. Consecutive number forms are one number: concatenate their decimal digits\n"
                      "(20 24 = 2024; 10 5 = 105; 2 0 5 = 205). POINT = decimal point (3 POINT 11 = 3.11).")
    lines = [g, "GRAMMAR (form NAME meaning):"]
    for e in order:
        if e["section"] == "grammar":
            name = e["key"][1:] if e["key"].startswith("_") else "P:" + (e["class"] or "") + " " + e["key"][1:].upper()
            lines.append(f"{forms[e['key']]} {name} {e['gloss']}")
    nums = [e for e in order if e["section"] == "number"]
    nums.sort(key=lambda e: int(e["key"][1:]))
    lines.append(f"NUMBERS 0-{len(nums) - 1} in order: " + " ".join(forms[e["key"]] for e in nums))
    lines.append("PHRASES (form class meaning):")
    for e in order:
        if e["section"] == "macro":
            lines.append(f"{forms[e['key']]} P:{e['class']} {e['gloss']}")
    lines.append("ROOTS (pairs: form meaning; one root covers noun/verb/modifier uses; names marked =name):")
    pairs = []
    for e in order:
        if e["section"] in ("core", "domain", "tech"):
            g = e["gloss"].replace(" ", "-") + ("=name" if e["section"] == "tech" else "")
            pairs.append(f"{forms[e['key']]} {g}")
    for i in range(0, len(pairs), 16):
        lines.append(" ".join(pairs[i:i + 16]))
    return "\n".join(lines) + "\n"


def evaluate(cfg: dict, toks: dict, pool: list[dict], ids: list[str], keep_detail: bool = False) -> dict:
    global N_NUM
    N_NUM = cfg["n_num"]
    entries = build_entries(n_num=cfg["n_num"], closed_conf=cfg["closed_conf"], macro_zipf=cfg["macro_zipf"],
                            domain_boost=cfg["domain_boost"])
    by_key = {e["key"]: e for e in entries}
    order = priority_order(entries)
    forms = assign_forms(order, pool)
    macro_exp = {k: exp for k, _, _, exp in MACROS}
    missing = set()
    for mid in ids:
        for em in (False, True):
            for kind, v in expand(dsl_tokens(MESSAGES[mid][0]), em, macro_exp):
                if kind == "key" and v not in by_key:
                    missing.add(v)
    if missing:
        raise SystemExit(f"missing lexicon keys: {sorted(missing)}")
    used_keys: list[str] = []
    for mid in ids:
        for kind, v in expand(dsl_tokens(MESSAGES[mid][0]), False, macro_exp):
            if kind == "key" and v not in used_keys:
                used_keys.append(v)

    # even-spread variant: used open-class entries spread evenly over the open-class ranks (projection.py style)
    closed_n = sum(1 for e in order if e["section"] in ("grammar", "number"))
    keys_in_order = [e["key"] for e in order]
    used_open = sorted((k for k in used_keys if by_key[k]["section"] not in ("grammar", "number")),
                       key=keys_in_order.index)
    n_open = len(order) - closed_n
    form_list = [forms[k] for k in keys_in_order]
    forms_spread = dict(forms)
    taken = {forms[k] for k in used_keys if by_key[k]["section"] in ("grammar", "number")}
    for i, k in enumerate(used_open):
        r = closed_n + int(i * n_open / len(used_open))
        while form_list[r] in taken or related(form_list[r], by_key[k]["gloss"] + " " + k) or (form_list[r], k) in VETO:
            r += 1
        taken.add(form_list[r])
        forms_spread[k] = form_list[r]

    variants = {"main": (False, forms), "macros_expanded": (True, forms), "even_spread": (False, forms_spread),
                "RELAXATION_raw_digits": (False, forms)}
    per = {v: {} for v in variants}
    rendered = {v: {} for v in variants}
    for v, (em, fm) in variants.items():
        for mid in ids:
            seq = expand(dsl_tokens(MESSAGES[mid][0]), em, macro_exp, raw_digits=(v == "RELAXATION_raw_digits"))
            text = render(seq, fm)
            rendered[v][mid] = text
            per[v][mid] = {"morphemes": sum(1 for k, _ in seq if k == "key"),
                           "raw_chunks": sum(1 for k, _ in seq if k == "raw"),
                           "tokens": {n: t.count(text) for n, t in toks.items()},
                           "tokens_leading_space": {n: t.count(" " + text) for n, t in toks.items()}}
    spec = spec_text(order, forms)
    out = {"cfg": cfg, "order": order, "forms": forms, "by_key": by_key, "used_keys": used_keys, "per": per,
           "rendered": rendered, "spec": spec, "spec_tokens": {n: t.count(spec) for n, t in toks.items()},
           "totals": {v: {n: sum(per[v][m]["tokens"][n] for m in ids) for n in toks} for v in variants},
           "totals_leading_space": {v: {n: sum(per[v][m]["tokens_leading_space"][n] for m in ids) for n in toks}
                                    for v in variants}}
    return out


CONFIGS = {
    # main: conservative frequency assumptions, digit forms 0-99, confidence/evidence phrases treated as grammar
    "A_num100": {"n_num": 100, "closed_conf": True, "macro_zipf": 4.0, "domain_boost": 0.0},
    "B_num10": {"n_num": 10, "closed_conf": True, "macro_zipf": 4.0, "domain_boost": 0.0},
    # sensitivity: assume codebook phrases and domain roots are much more frequent in agent traffic than in English
    "C_num10_agentfreq": {"n_num": 10, "closed_conf": True, "macro_zipf": 5.0, "domain_boost": 1.0},
    "D_num100_agentfreq": {"n_num": 100, "closed_conf": True, "macro_zipf": 5.0, "domain_boost": 1.0},
    # sensitivity: a Claude-optimised dialect (forms ordered by claude_legacy cost first; forms not hand-reviewed)
    "E_num10_claude_first": {"n_num": 10, "closed_conf": True, "macro_zipf": 4.0, "domain_boost": 0.0,
                             "pool_order": "claude_first"},
}
MAIN = "B_num10"


def main() -> None:
    toks = load_all()
    names = list(toks)
    corpus = {m["id"]: m for m in json.loads((HERE.parent / "corpus" / "ai_messages.json").read_text())}
    ids = sorted(MESSAGES)
    assert ids == [f"m{i:02d}" for i in range(2, 41, 2)], ids
    pool = load_pool()
    base = {mid: {n: {"en": toks[n].count(corpus[mid]["en"]), "en_terse": toks[n].count(corpus[mid]["en_terse"])}
                  for n in names} for mid in ids}
    tot_en = {n: sum(base[m][n]["en"] for m in ids) for n in names}
    tot_te = {n: sum(base[m][n]["en_terse"] for m in ids) for n in names}

    pool_claude = sorted(pool, key=lambda r: (r["cost"]["claude_legacy"], r["mean"], r["max"]))
    runs = {name: evaluate(cfg, toks, pool_claude if cfg.get("pool_order") == "claude_first" else pool, ids)
            for name, cfg in CONFIGS.items()}
    print(f"{'config':20} {'variant':16} " + " ".join(f"{n[:9]:>9}" for n in names))
    print(f"{'baseline':20} {'en':16} " + " ".join(f"{tot_en[n]:9}" for n in names))
    print(f"{'baseline':20} {'en_terse':16} " + " ".join(f"{tot_te[n]:9}" for n in names))
    for name, r in runs.items():
        for v in ("main", "macros_expanded", "even_spread", "RELAXATION_raw_digits"):
            print(f"{name:20} {v[:16]:16} " + " ".join(f"{r['totals'][v][n]:4}({r['totals'][v][n] / tot_te[n]:.2f})"
                                               for n in names))
        print(f"{name:20} {'main+lead_space':16} " + " ".join(
            f"{r['totals_leading_space']['main'][n]:4}({r['totals_leading_space']['main'][n] / tot_te[n]:.2f})" for n in names))
        print(f"{name:20} {'spec_tokens':16} " + " ".join(f"{r['spec_tokens'][n]:9}" for n in names))

    r = runs[MAIN]
    (HERE / "attempt_1_spec.txt").write_text(r["spec"])
    by_key, forms, order = r["by_key"], r["forms"], r["order"]
    sections_used: dict[str, list[str]] = {}
    for k in r["used_keys"]:
        sec = by_key[k]["section"]
        if k.startswith("@"):
            sec = "macro (closed: confidence/evidence)" if sec == "grammar" else "macro"
        sections_used.setdefault(sec, []).append(k)
    lexicon = {}
    for k in r["used_keys"]:
        e = by_key[k]
        if k.startswith("_"):
            g = f"[G {k[1:]}] {e['gloss']}"
        elif k.startswith("@"):
            g = f"[P:{e['class']}] {e['gloss']}"
        elif e["section"] == "number":
            g = f"[number] {e['gloss']}"
        elif e["section"] == "tech":
            g = f"[name] {e['gloss']}"
        else:
            g = e["gloss"]
        lexicon[forms[k]] = g
    form_cost = {k: {"form": forms[k], **{n: toks[n].count("the " + forms[k]) - toks[n].count("the") for n in names}}
                 for k in r["used_keys"]}
    totals = {}
    for n in names:
        row = {"en": tot_en[n], "en_terse": tot_te[n]}
        for v in ("main", "macros_expanded", "even_spread", "RELAXATION_raw_digits"):
            row[v] = r["totals"][v][n]
            row[v + "_vs_en_terse"] = round(r["totals"][v][n] / tot_te[n], 3)
            row[v + "_vs_en"] = round(r["totals"][v][n] / tot_en[n], 3)
        row["main_leading_space"] = r["totals_leading_space"]["main"][n]
        totals[n] = row
    wins = {n: sum(1 for m in ids if r["per"]["main"][m]["tokens"][n] < base[m][n]["en_terse"]) for n in names}
    ties = {n: sum(1 for m in ids if r["per"]["main"][m]["tokens"][n] == base[m][n]["en_terse"]) for n in names}
    secs = ("grammar", "number", "macro", "core", "domain", "tech")
    out = {
        "strategy": STRATEGY,
        "spec_summary": GRAMMAR_TEXT,
        "lexicon": lexicon,
        "messages": [{"id": mid, "encoded": r["rendered"]["main"][mid], "back_translation": MESSAGES[mid][1],
                      "dsl": MESSAGES[mid][0], "en": corpus[mid]["en"], "en_terse": corpus[mid]["en_terse"],
                      "tokens": r["per"]["main"][mid]["tokens"],
                      "en_terse_tokens": {n: base[mid][n]["en_terse"] for n in names},
                      "morphemes": r["per"]["main"][mid]["morphemes"]} for mid in ids],
        "measurement": {
            "main_config": MAIN, "config": CONFIGS[MAIN],
            "totals": totals,
            "per_message_wins_vs_en_terse": wins, "per_message_ties_vs_en_terse": ties,
            "morphemes_total": {v: sum(r["per"][v][m]["morphemes"] for m in ids) for v in ("main", "macros_expanded")},
            "spec": {"entries_total": len(order),
                     "entries_by_section": {s: sum(1 for e in order if e["section"] == s) for s in secs},
                     "closed_class_macros": sum(1 for e in order if e["section"] == "grammar" and e["key"].startswith("@")),
                     "spec_tokens": r["spec_tokens"],
                     "grammar_text_tokens": {n: toks[n].count(GRAMMAR_TEXT) for n in names}},
            "used_entries": {s: len(v) for s, v in sections_used.items()},
            "used_entries_list": sections_used,
            "used_form_cost": form_cost,
            "variants": {
                "main": "frequency-ranked forms (roots: wordfreq zipf; codebook phrases: assumed zipf 4.0; "
                        "confidence/evidence phrases: closed class)",
                "macros_expanded": "same forms, each phrase macro replaced by its expansion (ablation)",
                "even_spread": "used open-class entries spread evenly over open-class ranks (projection.py-style)",
                "main_leading_space": "main with one leading space before the message",
                "RELAXATION_raw_digits": "RELAXATION (breaks letters-only rule): numbers written as raw Arabic digits "
                                         "without a quote marker; everything else as main",
            },
            "sensitivity_configs": {name: {"cfg": rr["cfg"],
                                           "totals": {v: rr["totals"][v] for v in ("main", "macros_expanded", "even_spread", "RELAXATION_raw_digits")},
                                           "spec_tokens": rr["spec_tokens"]} for name, rr in runs.items()},
            "rendered_variants": {v: r["rendered"][v] for v in ("macros_expanded", "even_spread", "RELAXATION_raw_digits")},
            "per_message": r["per"],
            "baseline_per_message": base,
        },
    }
    (HERE / "attempt_1.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("\nMAIN", MAIN, "entries", len(order), "used:", {s: len(v) for s, v in sections_used.items()})
    print("wins/ties vs en_terse:", {n: f"{wins[n]}/{ties[n]}" for n in names})
    for mid in ids:
        t = r["per"]["main"][mid]["tokens"]
        print(mid, f"o200k {t['o200k']}/{base[mid]['o200k']['en_terse']} claude {t['claude_legacy']}/"
                   f"{base[mid]['claude_legacy']['en_terse']} sp {t['mistral_sp']}/{base[mid]['mistral_sp']['en_terse']}"
                   f" | {r['rendered']['main'][mid]}")


STRATEGY = ("Codebook / macro morphemes + spaced single-token forms (attempt 1, advocate). Telegraphic predicate-first "
            "grammar (~93 grammar markers), number forms, a ~80-entry phrase codebook of frequent agent-traffic phrases "
            "(status, requests, errors, hand-off, review, time, fused confidence x evidence), and ~2,200 roots "
            "(2,000 most frequent English content lemmas from wordfreq + ~190 work/software/data/research roots + 22 "
            "tech names). Forms come from a scan of all 7 tokenizer vocabularies (space-prefixed letter strings, max "
            "zipf < 3.0 in 11 languages, English zipf < 2.5, code identifiers and complete long words removed); the "
            "cheapest forms go to grammar, numbers and the confidence/evidence phrases, then roots and phrases by "
            "estimated frequency. Raw strings use a count-delimited quote marker (Q1/Q2/Q3 = next 1/2/3 chunks).")


if __name__ == "__main__":
    main()
