"""Attempt 1 lexicon: grammar markers, numbers, phrase macros (codebook), domain roots, tech names, core roots.

Every entry = (key, section, gloss, est_zipf). Forms are assigned later in order of priority:
closed class (grammar + numbers) first, then open class sorted by estimated frequency (est_zipf, descending).
Keys: '_X' grammar, '#n' number, '@x' macro, plain word = root.
"""
from __future__ import annotations

import math

from wordfreq import zipf_frequency

from core_attempt_1 import build_core

N_CORE = 2000

# ---------------------------------------------------------------- grammar (closed class), priority order
GRAMMAR = [
    ("_SEP", "end of clause/sentence (like '.')"),
    ("_CNT", "':' elaboration: namely / consisting of / which is / with content"),
    ("_AND", "and (between list items; between clauses only when needed)"),
    ("_NEG", "not (before predicate or NP)"),
    ("_PAST", "TAM past: did / -ed"),
    ("_QUES", "yes/no question (clause-final)"),
    ("_IS", "equative copula: is / = (NP IS NP)"),
    ("_TO", "to / into / toward (goal, recipient, target value)"),
    ("_IN", "in / at (place, container)"),
    ("_ON", "about / on (topic)"),
    ("_FOR", "for (purpose, beneficiary, duration)"),
    ("_WITH", "with / having"),
    ("_BY", "by (agent of passive; deadline)"),
    ("_OF", "of (head OF possessor/whole)"),
    ("_AT", "at (point: value, time)"),
    ("_FROM", "from"),
    ("_OR", "or / either...or"),
    ("_BUT", "but (contrast; starts clause)"),
    ("_CAUSE", "because (starts reason clause)"),
    ("_CONSE", "so / therefore (starts consequence clause)"),
    ("_IF", "if (condition clause; consequence starts at next TAM/verb/connective)"),
    ("_THEN", "then / next step"),
    ("_I", "I / me"),
    ("_YOU", "you"),
    ("_WE", "we / us"),
    ("_THEY", "they / them / singular they"),
    ("_IT", "it / that one"),
    ("_MY", "my"),
    ("_YOUR", "your"),
    ("_THEIR", "their"),
    ("_THIS", "this / these"),
    ("_THAT", "that / those"),
    ("_PROG", "TAM progressive: currently ...-ing (now)"),
    ("_FUT", "TAM future: will"),
    ("_DONE", "TAM/predicate completive: is done / finished"),
    ("_ALREADY", "TAM already / have ...-ed"),
    ("_NOTYET", "TAM not yet / have not ...-ed yet"),
    ("_STILL", "still"),
    ("_AGAIN", "again"),
    ("_CAN", "TAM can / able to"),
    ("_FAIL", "TAM could not / failed to"),
    ("_SHOULD", "TAM should"),
    ("_MUST", "TAM must / have to"),
    ("_MAY", "TAM may / might"),
    ("_HORT", "TAM let us / we should / I propose we"),
    ("_DONT", "do not (negative imperative)"),
    ("_NEVER", "never"),
    ("_PASS", "passive: subject undergoes V (is/was V-ed)"),
    ("_NO", "no / none of (quantifier)"),
    ("_ALL", "all / everything"),
    ("_ANY", "any / anything"),
    ("_SOME", "some / something"),
    ("_EACH", "each"),
    ("_EVERY", "every"),
    ("_OTHER", "other / another / else"),
    ("_ONLY", "only"),
    ("_MORE", "more / -er (comparative)"),
    ("_MOST", "most / -est (superlative)"),
    ("_LESS", "less / fewer"),
    ("_TOO", "too (excessively)"),
    ("_VERY", "very"),
    ("_ALSO", "also"),
    ("_NOW", "now"),
    ("_HERE", "here"),
    ("_FIRST", "first"),
    ("_LAST", "last"),
    ("_AFTER", "after"),
    ("_BEFORE", "before"),
    ("_THAN", "than"),
    ("_UNTIL", "until"),
    ("_WITHOUT", "without"),
    ("_INSTEAD", "instead of"),
    ("_EXCEPT", "except"),
    ("_PER", "per (rate)"),
    ("_APPROX", "about / approximately"),
    ("_WHAT", "what (question / embedded)"),
    ("_WHICH", "which (question / embedded)"),
    ("_WHO", "who"),
    ("_WHERE", "where"),
    ("_WHEN", "when"),
    ("_WHY", "why"),
    ("_HOW", "how (question / embedded: how X V Y)"),
    ("_YES", "yes"),
    ("_Q1", "quote: next 1 space-separated chunk is raw text"),
    ("_Q2", "quote: next 2 chunks are raw text"),
    ("_Q3", "quote: next 3 chunks are raw text"),
    ("_POINT", "decimal point"),
    ("_ORD", "ordinal: ORD n = n-th"),
    ("_TIMES", "n TIMES = n times"),
    ("_HUNDRED", "x100"),
    ("_THOUSAND", "x1000"),
    ("_MILLION", "x1000000"),
    ("_PERCENT", "percent"),
]

# ---------------------------------------------------------------- phrase macros (the codebook)
# (key, class, gloss, expansion-without-macro). class: S clause, NP, VP, M modifier/adverbial.
MACROS = [
    # status / progress
    ("@no_blockers", "S", "no blockers so far", "_NO blocker _NOW"),
    ("@in_progress", "M", "in progress", "_PROG"),
    ("@on_track", "M", "on track / on schedule", "_IN schedule"),
    ("@behind_schedule", "M", "behind schedule", "late"),
    ("@blocked_by", "VP", "is blocked by", "_PASS block _BY"),
    ("@waiting_for", "VP", "waiting for", "_PROG wait _FOR"),
    ("@all_done", "S", "everything is done", "_ALL _DONE"),
    ("@almost_done", "M", "almost done", "almost _DONE"),
    ("@ready_for_review", "M", "ready for review", "ready _FOR review"),
    ("@tests_pass", "S", "all tests pass", "_ALL test pass"),
    ("@tests_fail", "S", "some tests fail", "_SOME test fail"),
    ("@no_changes_needed", "S", "no changes needed", "_NO change need"),
    ("@next_step", "NP", "the next step", "next step"),
    ("@so_far", "M", "so far", "_UNTIL _NOW"),
    ("@as_planned", "M", "as planned", "_PASS plan"),
    ("@lit_search", "NP", "literature search", "literature search"),
    ("@status_update", "NP", "status update", "status update"),
    ("@first_draft", "NP", "first draft", "_FIRST draft"),
    # requests / instructions
    ("@please_confirm", "S", "please confirm", "confirm"),
    ("@let_me_know", "VP", "let me know", "tell _I"),
    ("@return_top", "VP", "return the top N most relevant (N follows)", "return _MOST relevant"),
    ("@one_sentence_summary", "NP", "one-sentence summary", "#1 sentence summary"),
    ("@short_summary", "NP", "short summary", "short summary"),
    ("@step_by_step", "M", "step by step", "step _BY step"),
    ("@asap", "M", "as soon as possible", "_MOST soon"),
    ("@keep_unchanged", "VP", "keep (NP) unchanged", "_DONT change"),
    ("@run_tests", "VP", "run the test suite", "run test"),
    ("@open_pr", "VP", "open a pull request", "open pull request"),
    ("@review_changes", "VP", "review the changes", "review change"),
    ("@make_sure", "VP", "make sure that", "ensure"),
    ("@double_check", "VP", "double-check", "check _AGAIN"),
    ("@for_backcompat", "M", "for backward compatibility", "_FOR backward compatible"),
    ("@in_order", "S", "proposed plan, steps strictly in this order:", "_HORT _CNT"),
    ("@does_that_work", "S", "does that work for you? / OK with you?", "agree _QUES"),
    ("@want_me_to", "VP", "do you want me to ...?", "_YOU want _I"),
    ("@your_call", "S", "your decision", "_YOUR decide"),
    # errors / problems
    ("@not_found", "S", "(it) does not exist / was not found", "_NEG exist"),
    ("@permission_denied", "S", "permission denied", "_NO permission"),
    ("@timed_out", "S", "(it) timed out", "timeout"),
    ("@out_of_memory", "S", "out of memory", "_NO memory"),
    ("@invalid_input", "NP", "invalid input", "wrong input"),
    ("@unexpected_error", "NP", "unexpected error", "error"),
    ("@my_prev_answer", "NP", "my previous answer", "_MY previous answer"),
    ("@root_cause", "NP", "root cause", "cause"),
    ("@likely_cause", "NP", "most likely cause (compound head: X likely_cause = most likely cause of X)", "_MOST likely cause"),
    ("@edge_case", "NP", "edge case", "edge case"),
    ("@stack_trace", "NP", "stack trace", "stack trace"),
    ("@error_message", "NP", "error message", "error message"),
    ("@side_effect", "NP", "side effect", "side effect"),
    # handoff / coordination
    ("@context_next_agent", "S", "context for the next agent:", "context _FOR next agent _CNT"),
    ("@pass_back", "VP", "I am passing (NP) back to you", "_PROG return _TO _YOU"),
    ("@needs_human_approval", "S", "(this) needs human approval", "need human approval"),
    ("@user_said", "S", "the user said:", "user said"),
    ("@per", "M", "according to (NP); at message end covers the whole message", "_FROM"),
    ("@for_your_review", "M", "for your review", "_FOR _YOUR review"),
    # review / evaluation
    ("@looks_good", "S", "looks good", "good"),
    ("@rest_correct", "S", "everything else is correct", "_ALL _OTHER correct"),
    ("@minor_issue", "NP", "minor issue", "small issue"),
    ("@add_source", "VP", "add a source / citation", "add source"),
    ("@needs_work", "S", "needs more work", "need _MORE work"),
    # time
    ("@later_this_week", "M", "later this week", "later _THIS week"),
    ("@by_end_of_day", "M", "by end of day", "_BY end _OF day"),
    ("@next_week", "M", "next week", "next week"),
    ("@this_week", "M", "this week", "_THIS week"),
    ("@at_the_end", "M", "at the end", "_AT end"),
    # confidence x evidence (fused)
    ("@conf_high", "S", "I am highly confident", "_I _VERY confident"),
    ("@conf_fair", "S", "I am fairly confident", "_I fair confident"),
    ("@conf_low", "S", "my confidence is low", "_MY confidence low"),
    ("@conf_unknown", "S", "I do not know / cannot tell", "_I _NEG know"),
    ("@conf_high_tool", "S", "highly confident, based on tool output (tool NP may follow)", "_VERY confident _FROM tool output"),
    ("@conf_fair_tool", "S", "fairly confident, based on tool output (tool NP may follow)", "fair confident _FROM tool output"),
    ("@conf_low_tool", "S", "low confidence, based on tool output", "confidence low _FROM tool output"),
    ("@conf_high_test", "S", "highly confident, verified by running it", "_VERY confident _PAST test"),
    ("@conf_high_docs", "S", "highly confident, per the documentation", "_VERY confident _FROM documentation"),
    ("@conf_fair_infer", "S", "fairly confident, inferred (not verified)", "fair confident _PASS infer"),
    ("@conf_low_infer", "S", "low confidence, inferred (not verified)", "confidence low _PASS infer"),
    # units
    ("@gpu_hour", "NP", "GPU hour(s)", "gpu hour"),
    ("@token_count", "NP", "token count", "token number"),
]

# ---------------------------------------------------------------- domain roots (work / software / data / research / agent ops)
DOMAIN_WORDS = """
code bug patch commit branch merge rebase repository deploy deployment compile dependency package library module
interface endpoint response server client database query schema column row index cache queue thread latency
throughput timeout retry exception crash log config environment variable parameter input output folder directory
path script command terminal container cluster node frontend backend refactor deprecation upgrade downgrade migrate
migration rollback backup restore permission authentication token credential encryption profiler benchmark
performance slowdown regression flaky coverage lint parse validate duplicate null overflow leak scan monitor alert
on_call incident outage uptime billing invoice subscription ticket requirement prototype mockup documentation
changelog dashboard spreadsheet pipeline workflow diff snippet syntax compiler runtime debug breakpoint stack heap
dataset label metric accuracy precision recall epoch batch inference prompt embedding finetune baseline outlier
distribution median variance correlation cluster visualization chart plot aggregate filter sort preprocess
experiment hypothesis significance measurement calculation formula statistic annotation evaluation hyperparameter
checkpoint gpu cpu api json csv sql url http
literature citation cite reference abstract summary evidence persuasive authoritative bias hedge consensus finding
methodology appendix outline proofread translate tone polite formal peer_reviewed journal transcript paraphrase
rewrite revise feedback relevant reliable confident output summary
subtask deadline milestone priority blocker handoff delegate assign agenda approval confirmation scope timeline
roadmap sprint backlog status progress compromise negotiate counteroffer instruction constraint preference
rejection shortlist workaround tradeoff stakeholder deliverable criteria checklist partial layout disk owner
infer verify reproduce escalate retrospective quota rate_limit compatible backward
""".split()

# frequent tech proper names that agents mention constantly
TECH = """python javascript typescript numpy pandas pytorch docker kubernetes git github linux postgres redis react
node npm pip aws azure gcp slack jira excel""".split()


def _zipf(word: str) -> float:
    w = word.replace("_", " ")
    return zipf_frequency(w, "en")


CLOSED_MACROS = {"@conf_high", "@conf_fair", "@conf_low", "@conf_unknown", "@conf_high_tool", "@conf_fair_tool",
                 "@conf_low_tool", "@conf_high_test", "@conf_high_docs", "@conf_fair_infer", "@conf_low_infer", "@per"}


def build_entries(n_num: int = 100, closed_conf: bool = True, macro_zipf: float = 4.0,
                  domain_boost: float = 0.0) -> list[dict]:
    """n_num: number forms 0..n_num-1 (10 = digits only, 100 = two-digit forms).
    closed_conf: confidence/evidence + PER macros are treated as grammar (closed class, cheapest forms).
    macro_zipf: assumed frequency (zipf) of the other phrase macros. domain_boost: added to domain/tech zipf."""
    entries: list[dict] = []
    seen: set[str] = set()

    def add(key, section, gloss, est, expansion=None, cls=None):
        if key in seen:
            return
        seen.add(key)
        entries.append({"key": key, "section": section, "gloss": gloss, "est_zipf": est,
                        "expansion": expansion, "class": cls})

    # closed class: grammar interleaved with small numbers, then larger numbers (all get the cheapest forms)
    small = [f"#{i}" for i in range(0, min(13, n_num))]
    for i, (k, g) in enumerate(GRAMMAR):
        add(k, "grammar", g, 99.0 - i * 0.01)
        if i == 30:
            for n in small:
                add(n, "number", n[1:], 98.0)
            if closed_conf:
                for k2, cls, g2, exp in MACROS:
                    if k2 in CLOSED_MACROS:
                        add(k2, "grammar", g2, 98.5, expansion=exp, cls=cls)
    for i in range(13, n_num):
        add(f"#{i}", "number", str(i), 97.0)
    # open class
    core = build_core(N_CORE)
    for w, z in core:
        add(w, "core", w, z)
    for w in DOMAIN_WORDS:
        add(w, "domain", w.replace("_", "-"), _zipf(w) + domain_boost)
    for w in TECH:
        add(w, "tech", w, _zipf(w) + domain_boost)
    for k, cls, g, exp in MACROS:
        add(k, "macro", g, macro_zipf, expansion=exp, cls=cls)
    return entries


def priority_order(entries: list[dict]) -> list[dict]:
    closed = [e for e in entries if e["section"] in ("grammar", "number")]
    opened = [e for e in entries if e["section"] not in ("grammar", "number")]
    closed.sort(key=lambda e: -e["est_zipf"])
    opened.sort(key=lambda e: (-e["est_zipf"], e["key"]))
    return closed + opened


if __name__ == "__main__":
    es = build_entries()
    from collections import Counter
    print(len(es), Counter(e["section"] for e in es))
