"""attempt_2: build the general lexicon, assign forms, encode the 20 test messages, measure on 7 tokenizers.

Lexicon = F (function words, numbers) + G (top N_G general English content lemmas by wordfreq, a2_rank.json;
        only lemmas found in the web2/gcide word lists or in D, so names/brands/slang are left out)
        + D (domain block: AI / software / data / research / coordination terms, fixed list below).
Forms come from a2_forms.json (non-word pool), ordered so that claude_legacy stays single-token longest
(mistral_sp is sacrificed first). Entries take forms in lexicon order; a form is skipped for an entry when it
looks related to the gloss (shared first 3 letters, or one contains the other).

Scenarios (only the position of D changes):
  A_conservative : F, G (by rank), then D terms not already in G (by English zipf)  -> domain terms get the worst forms
  B_domain_aware : F, G[:400], D terms not in G[:400], rest of G                     -> domain terms ranked like
                                                                                       frequent words
Outputs: a2_lexicon_<scenario>.json, a2_spec_<scenario>.txt (full spec text, for size), a2_results.json
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from toklib import load_all  # noqa: E402
from wordfreq import zipf_frequency  # noqa: E402
from a2_glosses import CLASS, MESSAGES  # noqa: E402

N_G = 2000

F = [  # key, class, gloss (spec text)
    ("DECL", "MODE", "mode statement (default); dropped subject = I"),
    ("IMP", "MODE", "mode request/command; dropped subject = you"),
    ("HORT", "MODE", "mode proposal 'let us'; dropped subject = we"),
    ("SUGQ", "MODE", "mode proposal asking agreement 'shall we ..., OK?'; dropped subject = we"),
    ("DELIB", "MODE", "mode 'should I ...?' asking for a decision; dropped subject = I"),
    ("Q", "MODE", "mode yes/no question; dropped subject = I"),
    ("NEG", "OP", "not"), ("PASS", "OP", "passive: subject is the patient"), ("PROG", "OP", "ongoing now"),
    ("FUT", "OP", "future"), ("PAST", "OP", "past (for states)"), ("NOTYET", "OP", "not yet"),
    ("STILL", "OP", "still"), ("CAN", "OP", "can"), ("CANNOT", "OP", "cannot / could not"),
    ("MUST", "OP", "should / must"), ("PROB", "OP", "probably"),
    ("MOST", "DEG", "most"), ("MORE", "DEG", "more / -er"), ("LESS", "DEG", "less"), ("TOO", "DEG", "too"),
    ("FAIRLY", "DEG", "fairly"), ("VERY", "DEG", "very"),
    ("BUT", "CONJ", "but"), ("OR", "CONJ", "or"), ("IF", "CONJ", "if (next clause is the condition)"),
    ("BECAUSE", "CONJ", "because (next clause is the reason)"), ("THEN", "CONJ", "then (sequence)"),
    ("SO", "CONJ", "so"), ("ALTHOUGH", "CONJ", "although"),
    ("ET", "CONJ", "and (+NP: NP list; +V/OP: clause sharing the subject, inside the current conjunct)"),
    ("TO", "P", "to"), ("FROM", "P", "from / based on"), ("WITH", "P", "with"), ("WITHOUT", "P", "without"),
    ("ABOUT", "P", "about (+NP or +clause)"), ("BY", "P", "by (agent)"), ("BYTIME", "P", "by (deadline)"),
    ("AT", "P", "at"), ("IN", "P", "in"), ("ON", "P", "on"), ("FOR", "P", "for"), ("AFTER", "P", "after"),
    ("BEFORE", "P", "before"), ("THAN", "P", "than (+NP or +clause)"), ("UNTIL", "P", "until"),
    ("DURING", "P", "during"),
    ("I", "PRO", "I"), ("YOU", "PRO", "you"), ("WE", "PRO", "we"), ("THEY", "PRO", "they"),
    ("IT", "PRO", "it (thing)"), ("THAT", "PRO", "that (proposition / plan)"), ("ALL", "PRO", "everything"),
    ("SOMEONE", "PRO", "someone"),
    ("MY", "POSS", "my"), ("YOUR", "POSS", "your"), ("OUR", "POSS", "our"), ("THEIR", "POSS", "their"),
    ("ITS", "POSS", "its"),
    ("THIS", "DET", "this"), ("EVERY", "DET", "every"), ("ANY", "DET", "any"), ("SOME", "DET", "some"),
    ("ONLY", "DET", "only"),
    ("EACH", "ADV", "each (distributive)"), ("SOFAR", "ADV", "so far"), ("FIRSTLY", "ADV", "first (in order)"),
    ("LASTLY", "ADV", "at the end"), ("ALSO", "ADV", "also"), ("TWICE", "ADV", "twice"),
    ("MOSTLY", "ADV", "mostly"),
    ("WHICH", "WH", "which"), ("WHAT", "WH", "what"), ("WHO", "WH", "who"), ("WHERE", "WH", "where"),
    ("WHEN", "WH", "when"), ("HOW", "WH", "how"), ("WHY", "WH", "why"),
    ("LK", "STR", "of (X LK Y = Y of X)"), ("REL", "STR", "relative clause on the preceding NP (gap = missing role)"),
    ("PD", "STR", "clause boundary (only where two nouns would otherwise compound)"),
    ("QT", "STR", "raw span: next chunk + following chunks with uppercase/digit/symbol"),
    ("EQ", "STR", "is (copula, 1 object)"), ("NMLZ", "STR", "nominalizer"),
] + [(f"d{i}", "NUM", str(i)) for i in range(10)] + [(f"d{i}", "NUM", str(i)) for i in range(10, 100, 10)] + [
    ("HUNDRED", "NUM", "x100"), ("THOUSAND", "NUM", "x1000"), ("MILLION", "NUM", "x1e6"),
    ("POINT", "NUM", "decimal / version point; digits after it are read one by one"),
]

# Domain block: AI / software / data / research / coordination vocabulary (general, not limited to the corpus).
D = """api app server client database query document input output cache token model prompt agent tool file folder directory path url config
configuration setting dataset schema column row table field record log logging error exception warning bug fix patch
commit branch merge deploy deployment build release version upgrade downgrade dependency library package module script
test benchmark metric latency throughput memory cpu gpu disk network request response endpoint timeout retry backoff
queue thread process job task pipeline workflow frontend backend layout interface parameter variable integer string
array index search scan parse format encode compile runtime profiler slowdown regression crash deprecation compatibility
migration refactor permission credential account login password billing invoice budget cost deadline estimate schedule
milestone priority blocker ticket issue repository documentation readme changelog snapshot backup restore rollback
duplicate checksum hash encryption compression upload download install configure enable disable flag toggle option
default override fallback cluster node container image instance region storage bucket quota limit rate throttle trigger
event webhook notification alert monitor dashboard chart graph plot visualization spreadsheet csv report summary draft
outline citation cite reference source paper study survey experiment hypothesis result finding figure statistics sample
average median variance outlier correlation accuracy precision recall confidence probability evidence claim argument
conclusion review reviewer peerreviewed feedback approve approval reject confirmation confirm propose proposal negotiate
handoff assign delegate subtask plan goal requirement constraint specification user customer stakeholder owner
maintainer engineer developer oncall incident outage escalate verify validate validation measurement calculation compute
calculate reliable unreliable ambiguous clarify clarification assumption infer inference context instruction paraphrase
translate workingmemory embedding vector training finetune evaluation rubric score threshold baseline ablation prototype
demo mockup wireframe typo lint coverage mock fixture syntax semantic tokenizer deduplicate normalize aggregate filter
sort join export import sync backfill archive delete rename timestamp timezone locale encoding""".split()
ZIPF_ALIAS = {"peerreviewed": "peer-reviewed", "workingmemory": "working memory", "oncall": "on-call"}


# Forms skipped after manual review: related meaning to the entry that would have received them (sco=score->result,
# syll=syllogism->argument, opin=opinion->say, volunte->ready, reco=record->file, restr=restrict->fixed,
# milit->service, incent=incentive->cause, ult=ultimo->deadline, murm=murmur->think), number lookalikes
# (doub=double, zwe=zwei, segu=segundo) and abbreviations of other lexicon concepts (calc, caus, memor, req, addr, summ).
MANUAL_SKIP = set("""sco syll opin volunte reco restr milit incent ult murm doub zwe segu calc caus memor req addr summ
requ repro komunik retorn depr segreg egy cient extr pergunt afirm probabil integr efect conse imper neur puzz cycl
pierws wszyst subdir prud zgod acord synthes dirs nouve compagn cuar mezz prec chron necess transl anticip calib miscon
preci agrup aprob delim attrib preg enumer nuest configur letz trabaj scri tiem rencontr modific explor corrobor evid
redund inaccur kube encontr uyg improb inp recal remed encuent fich errone surve recher selecion noss wasm acerc aprov
cuant doubl autoc formul incor sve jorn invit llen adicion pued encont dedu giorn cinqu irres solic bestimm htt arriv lucr
approxim datab accep inspe nied asent unanim coeff nije timp incr serde konfl nond insurg lesb inqui manej uncert includ baj
behand demasi odpowied disreg cudd ktor retrie nostr archa accessor empres tomto daug afect fij cinc uten manj dodat beper muj koj arbet chied ques""".split())
# Review rule: a form of 4+ letters that is the start of the gloss of any entry used in the test messages, or of an
# English function word, is not assigned (estim->estimate, relev->relevant, probl->problem, inaccur->inaccurate...).
# STRICT=1 applies the same rule against every gloss in the lexicon (sensitivity variant, costs more tokens).
STRICT = os.environ.get("A2_STRICT") == "1"
FUNC_GLOSS = """which what where when because after before about without until than every only this that they again
first last never always maybe probably""".split()


FUNC_CLASSES = {"MODE", "OP", "DEG", "CONJ", "P", "PRO", "POSS", "DET", "ADV", "WH", "NUM", "STR"}


def related(form, gloss):
    g = gloss.lower().replace(" ", "")
    return form[:3] == g[:3] or form in g or (len(g) >= 3 and g in form)


def form_order():
    rows = json.loads((HERE / "a2_forms.json").read_text())
    names = list(rows[0]["costs"])

    def key(r):
        c = r["costs"]
        others = [c[n] for n in names if n != "mistral_sp"]
        return (sum(1 for v in others if v > 1), c["claude_legacy"], sum(others), c["mistral_sp"], len(r["form"]),
                r["form"])
    rows.sort(key=key)
    return rows


def lexicon_order(scenario):
    rank = json.loads((HERE / "a2_rank.json").read_text())
    fkeys = {k.lower() for k, _, _ in F}
    dset_all = set(D)
    general = [w for w, (_, in_dict) in sorted(rank.items(), key=lambda x: x[1][0])
               if w not in fkeys and (in_dict or w in dset_all)][:N_G]
    dz = sorted(set(D), key=lambda w: -zipf_frequency(ZIPF_ALIAS.get(w, w), "en"))
    if scenario == "A_conservative":
        gset = set(general)
        content = general + [w for w in dz if w not in gset]
    else:
        head = general[:400]
        hset = set(head)
        dom = [w for w in dz if w not in hset]
        dset = set(dom)
        content = head + dom + [w for w in general[400:] if w not in dset]
    return [(k, c, g) for k, c, g in F] + [(w, CLASS.get(w, "?"), w) for w in content]


def build(scenario):
    forms = form_order()
    entries = lexicon_order(scenario)
    if STRICT:
        watch = [g for _, c, g in entries if c not in FUNC_CLASSES]
    else:
        watch = sorted({t for _, seq, _ in MESSAGES for t in seq if isinstance(t, str) and t[:1].islower()})
    watch = [w.replace(" ", "") for w in watch] + FUNC_GLOSS + [w for w in ZIPF_ALIAS.values()]
    look = {f["form"] for f in forms if len(f["form"]) >= 4 and any(g.startswith(f["form"]) and g != f["form"]
                                                                    for g in watch)}
    used, lex = set(), {}
    fi = 0
    for idx, (key, cls, gloss) in enumerate(entries):
        j = fi
        while (forms[j]["form"] in used or forms[j]["form"] in MANUAL_SKIP or forms[j]["form"] in look
               or related(forms[j]["form"], gloss)):
            j += 1
        f = forms[j]
        used.add(f["form"])
        lex[key] = {"form": f["form"], "class": cls, "gloss": gloss, "index": idx, "costs": f["costs"]}
        while fi < len(forms) and forms[fi]["form"] in used:
            fi += 1
    return lex


def spec_text(lex):
    """Full spec as it would be given in context: grammar + lexicon grouped by class ('form gloss, ...')."""
    grammar = (HERE / "a2_grammar.txt").read_text()
    groups = {}
    for key, e in lex.items():
        groups.setdefault(e["class"], []).append(f"{e['form']} {e['gloss']}")
    lines = [grammar, "LEXICON (form gloss). Content entries of unknown class '?' would carry their class in the "
             "real spec, grouped like the others."]
    for cls, items in groups.items():
        lines.append(f"[{cls}] " + ", ".join(items))
    return "\n".join(lines)


def encode(lex, seq):
    out = []
    for t in seq:
        if isinstance(t, tuple):
            out.append(t[1])
        else:
            if t not in lex:
                raise KeyError(f"not in lexicon: {t}")
            out.append(lex[t]["form"])
    return " ".join(out)


def main():
    toks = load_all()
    corpus = {m["id"]: m for m in json.loads((HERE.parent / "corpus" / "ai_messages.json").read_text())}
    ids = [m[0] for m in MESSAGES]
    res = {"tokenizers": list(toks), "baseline": {}, "scenarios": {}}
    for k in ["en", "en_terse"]:
        res["baseline"][k] = {n: sum(t.count(corpus[i][k]) for i in ids) for n, t in toks.items()}
        res["baseline"][k + "_per_msg"] = {i: {n: t.count(corpus[i][k]) for n, t in toks.items()} for i in ids}
    for sc in ["A_conservative", "B_domain_aware"]:
        lex = build(sc)
        missing = sorted({t for _, seq, _ in MESSAGES for t in seq if isinstance(t, str) and t not in lex})
        if missing:
            print("MISSING", sc, missing)
            continue
        suf = "_strict" if STRICT else ""
        (HERE / f"a2_lexicon_{sc}{suf}.json").write_text(json.dumps(lex, indent=0))
        spec = spec_text(lex)
        (HERE / f"a2_spec_{sc}{suf}.txt").write_text(spec)
        enc = {mid: encode(lex, seq) for mid, seq, _ in MESSAGES}
        per = {mid: {n: t.count(s) for n, t in toks.items()} for mid, s in enc.items()}
        tot = {n: sum(per[m][n] for m in per) for n in toks}
        n_morph = sum(sum(1 for t in seq if not isinstance(t, tuple)) for _, seq, _ in MESSAGES)
        res["scenarios"][sc] = {
            "encoded": enc, "per_msg": per, "total": tot, "n_morphemes_excl_raw": n_morph,
            "ratio_vs_en": {n: round(tot[n] / res["baseline"]["en"][n], 3) for n in toks},
            "ratio_vs_en_terse": {n: round(tot[n] / res["baseline"]["en_terse"][n], 3) for n in toks},
            "lexicon_size": len(lex),
            "spec_tokens": {n: t.count(spec) for n, t in toks.items()},
            "used_entries": {t: lex[t] for _, seq, _ in MESSAGES for t in seq if isinstance(t, str)},
        }
        print(sc, "lexicon", len(lex), "morphemes(excl raw)", n_morph)
        print("  total   ", tot)
        print("  vs en_terse", res["scenarios"][sc]["ratio_vs_en_terse"])
        print("  vs en      ", res["scenarios"][sc]["ratio_vs_en"])
        print("  spec tokens", res["scenarios"][sc]["spec_tokens"])
    print("baseline en      ", res["baseline"]["en"])
    print("baseline en_terse", res["baseline"]["en_terse"])
    (HERE / ("a2_results_strict.json" if STRICT else "a2_results.json")).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
