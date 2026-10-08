"""Independent re-implementation of projection.py (claims C3, C4).

Written from the gloss conventions in corpus/gloss_*.json 'assumptions', not by importing projection.py.
Checks:
  1. S0/S1 morpheme counts per message vs the glossers' declared total_strict / total_elided.
  2. Pragmatic clusters: ordering, and how many clauses keep >= 2 non-default markers (what S2 fusion could save).
  3. Full token totals for S0..S5 with an independently built lexicon, compared to results/projection.json.
  4. Sensitivity runs (bias checks).

Run from experiments/tokenization:  python3 verify/v_projection.py
"""
import itertools
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from toklib import load_all  # noqa: E402
from wordfreq import zipf_frequency  # noqa: E402

toks = load_all()
NAMES = list(toks)
corpus = {m["id"]: m for m in json.loads((ROOT / "corpus" / "ai_messages.json").read_text())}
G = {k: json.loads((ROOT / "corpus" / f"gloss_{k}.json").read_text()) for k in (1, 2)}
PROJ = json.loads((ROOT / "results" / "projection.json").read_text())
BASE = json.loads((ROOT / "results" / "baseline.json").read_text())["per_message"]

# --- gloss conventions (from each file's 'assumptions')
PRAG1 = re.compile(r"^AFF:(SA|CF|EV)\.")
DEF1 = {"AFF:SA.assert", "AFF:CF.high", "AFF:EV.observed"}
PRAG2_VALS = {"ASRT", "CMD", "QUES", "PROP", "REQ", "HIGH", "LOW", "CERT", "OBS", "TOOL", "USR", "INF"}
ACT2 = {"ASRT", "CMD", "QUES", "PROP", "REQ"}


def is_prag(k, lab):
    if k == 1:
        return bool(PRAG1.match(lab))
    return lab.startswith("AFF:") and lab[4:].rstrip("*") in PRAG2_VALS


def is_default(k, lab):
    return lab in DEF1 if k == 1 else lab.endswith("*")


def tokenize_gloss(s):
    out, i = [], 0
    s = s.replace("|", " ")
    while i < len(s):
        if s[i].isspace():
            i += 1
            continue
        m = re.match(r'(RAW|STR):"([^"]*)"', s[i:])
        if m:
            out.append(("raw", m.group(2)))
            i += m.end()
            continue
        j = i
        while j < len(s) and not s[j].isspace():
            j += 1
        out.append(("lab", s[i:j]))
        i = j
    return out


def number_parts(lab):
    """returns ('marker'|'digit'|'point'|None, value)"""
    if lab == "NUM" or lab == "NUM:#":
        return "marker", ""
    if lab in ("DIG:point", "NUM:pt"):
        return "point", "."
    m = re.fullmatch(r"(DIG|NUM):(\d+)", lab)
    if m:
        return "digit", m.group(2)
    return None, None


def scenario_seq(k, items, scen):
    """items -> list of ('m', label) | ('raw', text) | ('dig', text)."""
    lvl = ["S0", "S1", "S2", "S3", "S4", "S5"].index(scen)
    out = []
    i = 0
    while i < len(items):
        typ, lab = items[i]
        if typ == "raw":
            out.append(("raw", lab))
            i += 1
            continue
        if lab.startswith("ZERO:"):
            i += 1
            continue
        if is_prag(k, lab):
            j = i
            cluster = []
            while j < len(items) and items[j][0] == "lab" and is_prag(k, items[j][1]):
                cluster.append(items[j][1])
                j += 1
            if lvl == 0:
                out += [("m", c) for c in cluster]
            elif lvl == 1:
                out += [("m", c) for c in cluster if not is_default(k, c)]
            else:
                nd = sorted(c for c in cluster if not is_default(k, c))
                if nd:
                    out.append(("m", "FUSED[" + "+".join(nd) + "]"))
            i = j
            continue
        if lvl >= 3 and lab in ("AFF:AGT", "AFF:PAT", "AFF:THM"):
            i += 1
            continue
        if lvl >= 4 and lab in ("AFF:LNK", "AFF:ATR"):
            i += 1
            continue
        kind, val = number_parts(lab)
        if lvl >= 5 and kind:
            if kind == "marker" or not out or out[-1][0] != "dig":
                out.append(("dig", ""))
            out[-1] = ("dig", out[-1][1] + val)
            i += 1
            continue
        out.append(("m", lab))
        i += 1
    return [x for x in out if not (x[0] == "dig" and x[1] == "")]


SCEN = ["S0", "S1", "S2", "S3", "S4", "S5"]
PNAME = {"S0": "S0_strict", "S1": "S1_elided", "S2": "S2_fused", "S3": "S3_positional", "S4": "S4_no_linker",
         "S5": "S5_raw_digits"}

print("=" * 70)
print("1. declared totals vs recount")
for k, g in G.items():
    bad_s, bad_e = [], []
    sums = Counter()
    for m in g["messages"]:
        items = tokenize_gloss(m["gloss_strict"])
        s0 = sum(1 for t, _ in scenario_seq(k, items, "S0") if t == "m")
        s1 = sum(1 for t, _ in scenario_seq(k, items, "S1") if t == "m")
        sums["s0"] += s0
        sums["s1"] += s1
        sums["decl_strict"] += m["total_strict"]
        sums["decl_elided"] += m["total_elided"]
        comp = m["roots"] + m["affixes"] + m["number_morphemes"] + m["marker_morphemes"]
        if comp != m["total_strict"]:
            print(f"  gloss{k} {m['id']}: roots+affixes+num+mrk={comp} != total_strict {m['total_strict']}")
        if s0 != m["total_strict"]:
            bad_s.append((m["id"], s0, m["total_strict"]))
        if s1 != m["total_elided"]:
            bad_e.append((m["id"], s1, m["total_elided"]))
        raws = [x for t, x in items if t == "raw"]
        if raws != m["foreign_strings"]:
            print(f"  gloss{k} {m['id']}: raw strings {raws} != foreign_strings {m['foreign_strings']}")
    print(f" gloss {k}: recount S0 {sums['s0']} vs declared total_strict {sums['decl_strict']}; "
          f"S1 {sums['s1']} vs declared total_elided {sums['decl_elided']}")
    print(f"   per-message S0 mismatches: {bad_s}")
    print(f"   per-message S1 mismatches: {bad_e}")

print("=" * 70)
print("2. pragmatic clusters")
for k, g in G.items():
    sizes, nd_hist, order = Counter(), Counter(), Counter()
    split_by_act_rule = 0
    for m in g["messages"]:
        items = tokenize_gloss(m["gloss_strict"])
        i = 0
        while i < len(items):
            if items[i][0] == "lab" and is_prag(k, items[i][1]):
                j = i
                cl = []
                while j < len(items) and items[j][0] == "lab" and is_prag(k, items[j][1]):
                    cl.append(items[j][1])
                    j += 1
                sizes[len(cl)] += 1
                nd = [c for c in cl if not is_default(k, c)]
                nd_hist[len(nd)] += 1
                order[tuple(re.sub(r"\..*|\*$", "", c[4:]) if k == 1 else ("ACT" if c[4:].rstrip("*") in ACT2 else "x") for c in cl)] += 1
                i = j
            else:
                i += 1
    print(f" gloss {k}: cluster sizes {dict(sizes)}; non-default markers per cluster {dict(sorted(nd_hist.items()))}")
    print(f"   cluster label order patterns: {dict(order)}")

print("=" * 70)
print("3. token totals (independent lexicon build)")
VOW, CON = "aeiou", "bcdfghjklmnpqrstvwxyz"
LANGS = ["en", "es", "de", "fr", "it", "pt", "nl", "tr", "id", "pl", "sv"]
SHAPES = ["CV", "CVC", "CCV", "CVCC", "CCVC", "CVCV"]
CACHE = HERE / "form_costs_cache.json"
if CACHE.exists():
    forms = json.loads(CACHE.read_text())
else:
    forms = []
    ctx_n = {n: t.count("the") for n, t in toks.items()}
    for sh in SHAPES:
        for tup in itertools.product(*[CON if c == "C" else VOW for c in sh]):
            f = "".join(tup)
            z = max(zipf_frequency(f, l) for l in LANGS)
            if z >= 3.0:
                continue
            cost = {n: t.count("the " + f) - ctx_n[n] for n, t in toks.items()}
            forms.append({"form": f, "zipf": z, "cost": cost})
    CACHE.write_text(json.dumps(forms))
print(" candidate forms:", len(forms), "(projection.json meta says", PROJ["meta"]["n_candidate_forms"], ")")


def order_forms(forms, key="mean"):
    if key == "mean":
        k = lambda r: (statistics.mean(r["cost"].values()), max(r["cost"].values()), r["zipf"], len(r["form"]), r["form"])
    else:
        k = lambda r: (r["cost"][key], statistics.mean(r["cost"].values()), r["zipf"], len(r["form"]), r["form"])
    return sorted(forms, key=k)


def build_lex(seqs, ordered, n_closed=150, n_roots=1000):
    freq = Counter(x for s in seqs for t, x in s if t == "m")
    closed = sorted([x for x in freq if not x.startswith("ROOT:")], key=lambda x: (-freq[x], x))
    roots = sorted([x for x in freq if x.startswith("ROOT:")], key=lambda x: (-freq[x], x))
    assert len(closed) <= n_closed
    lex = {x: ordered[i]["form"] for i, x in enumerate(closed)}
    step = n_roots / max(len(roots), 1)
    for i, x in enumerate(roots):
        lex[x] = ordered[n_closed + int(i * step)]["form"]
    return lex, len(closed), len(roots)


def render(seq, lex):
    return " ".join(lex[x] if t == "m" else x for t, x in seq)


def run(ordered, label, n_closed=150, n_roots=1000, scen_list=SCEN, compare=False, show=True):
    res = {}
    for k, g in G.items():
        for sc in scen_list:
            seqs = [scenario_seq(k, tokenize_gloss(m["gloss_strict"]), sc) for m in g["messages"]]
            lex, nc, nr = build_lex(seqs, ordered, n_closed, n_roots)
            tot = {n: 0 for n in NAMES}
            for m, s in zip(g["messages"], seqs):
                txt = render(s, lex)
                for n, t in toks.items():
                    tot[n] += t.count(txt)
            nm = sum(1 for s in seqs for t, _ in s if t == "m")
            res[(k, sc)] = (nm, tot, nc, nr)
            if compare:
                p = PROJ["glosses"][str(k)][PNAME[sc]]
                diff = {n: tot[n] - p["tokens"][n] for n in NAMES if tot[n] != p["tokens"][n]}
                print(f"  gloss{k} {sc}: morphemes {nm} (proj {p['morphemes']}), closed labels {nc}, roots {nr}; "
                      f"token diffs vs projection.json: {diff or 'none'}")
    if show:
        en = {n: sum(BASE[i][n]["en"] for i in corpus) for n in NAMES}
        te = {n: sum(BASE[i][n]["en_terse"] for i in corpus) for n in NAMES}
        print(f" [{label}]  cells = tokens (x en, x en_terse)")
        for (k, sc), (nm, tot, nc, nr) in res.items():
            print(f"  g{k} {sc} m/msg {nm / 40:5.1f} | " + " | ".join(
                f"{n} {tot[n]} ({tot[n] / en[n]:.2f},{tot[n] / te[n]:.2f})" for n in ["o200k", "claude_legacy", "llama3", "mistral_sp"]))
    return res


ordered = order_forms(forms)
print(" mean cost closed[0:150]:", {n: round(statistics.mean(f["cost"][n] for f in ordered[:150]), 3) for n in NAMES})
print(" mean cost roots[150:1150]:", {n: round(statistics.mean(f["cost"][n] for f in ordered[150:1150]), 3) for n in NAMES})
base_res = run(ordered, "replication", compare=True)

# hand check: one rendered message, pieces per tokenizer
print("=" * 70)
print("4. hand check of rendered m01 / m05 (gloss 1, S5) and m22 (gloss 2, S5)")
for k, mid in [(1, "m01"), (1, "m05"), (2, "m22")]:
    g = G[k]
    seqs = [scenario_seq(k, tokenize_gloss(m["gloss_strict"]), "S5") for m in g["messages"]]
    lex, _, _ = build_lex(seqs, ordered)
    idx = [m["id"] for m in g["messages"]].index(mid)
    txt = render(seqs[idx], lex)
    print(f" gloss{k} {mid} S5: {txt!r}")
    print(f"   en: {corpus[mid]['en']!r}")
    print(f"   en_terse: {corpus[mid]['en_terse']!r}")
    for n in ["o200k", "claude_legacy", "mistral_sp"]:
        p = toks[n].pieces(txt)
        print(f"   {n}: {len(p)} tokens  {'|'.join(p)}")
        print(f"      en_terse {toks[n].count(corpus[mid]['en_terse'])}, en {toks[n].count(corpus[mid]['en'])}")

print("=" * 70)
print("5. sensitivity (bias checks), S4 and S5 only")
S45 = ["S1", "S4", "S5"]
# a) tokenizer-specific lexicon (what if the language only had to be cheap for one tokenizer)
for key in ["o200k", "claude_legacy"]:
    r = run(order_forms(forms, key), f"lexicon ordered by {key} cost only", scen_list=S45)
# b) root lexicon of 300 or 3000 instead of 1000
run(ordered, "root lexicon 300 (fewer roots, cheaper forms)", n_roots=300, scen_list=S45)
run(ordered, "root lexicon 3000", n_roots=3000, scen_list=S45)
# c) relaxed word filter zipf < 4.0 (needs a separate candidate list)
