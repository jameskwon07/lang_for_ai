"""Extra bias checks on the projection (C3): run after v_projection.py (uses its cache and functions).

  a. tokens per morpheme in the real projected texts (raw strings and digit strings removed)
  b. message-initial penalty: the first morpheme has no leading space, forms were picked for ' form'
  c. share of tokens spent on RAW/STR foreign strings that keep non a-z characters in every scenario
  d. word-filter sensitivity: zipf < 4.0 and no filter
  e. break-even vs en_terse: how many morphemes per message would the language need

Run from experiments/tokenization:  python3 verify/v_projection_extra.py
"""
import contextlib
import io
import itertools
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
with contextlib.redirect_stdout(io.StringIO()):
    import v_projection as V  # noqa: E402  (re-runs the replication silently, reuses cache)
from wordfreq import zipf_frequency  # noqa: E402

toks, G, NAMES = V.toks, V.G, V.NAMES
FOCUS = ["o200k", "cl100k", "claude_legacy", "llama3", "llama4", "mistral_tekken", "mistral_sp"]
en = {n: sum(V.BASE[i][n]["en"] for i in V.corpus) for n in NAMES}
te = {n: sum(V.BASE[i][n]["en_terse"] for i in V.corpus) for n in NAMES}
ordered = V.order_forms(V.forms)

print("a/b/c. per-scenario decomposition (sum over 40 messages)")
for k, g in G.items():
    for sc in ["S1", "S4", "S5"]:
        seqs = [V.scenario_seq(k, V.tokenize_gloss(m["gloss_strict"]), sc) for m in g["messages"]]
        lex, _, _ = V.build_lex(seqs, ordered)
        nm = sum(1 for s in seqs for t, _ in s if t == "m")
        row = []
        for n in ["o200k", "claude_legacy", "mistral_sp"]:
            t = toks[n]
            full = sum(t.count(V.render(s, lex)) for s in seqs)
            lex_only = sum(t.count(" ".join(lex[x] for tt, x in s if tt == "m")) for s in seqs)
            raw_tok = sum(t.count("the " + x) - t.count("the") for s in seqs for tt, x in s if tt == "raw")
            lead = sum(t.count(" " + V.render(s, lex)) for s in seqs) if n != "mistral_sp" else full
            row.append(f"{n}: total {full}, morpheme-only tpm {lex_only / nm:.3f}, raw-string tokens {raw_tok} "
                       f"({raw_tok / full:.1%}), with leading space {lead} (initial penalty {full - lead})")
        print(f" g{k} {sc} morphemes {nm}")
        for r in row:
            print("    " + r)

# raw strings: how many non a-z characters do they contain?
raw_all = [x for k, g in G.items() for m in g["messages"] for t, x in V.tokenize_gloss(m["gloss_strict"]) if t == "raw"]
print(" raw strings (both glossers):", len(raw_all), "chars", sum(map(len, raw_all)),
      "non-a-z chars", sum(1 for s in raw_all for c in s if not ("a" <= c <= "z")))

print()
print("d. word-filter sensitivity (rebuild candidate list with a different zipf cut)")
LANGS = V.LANGS
cache = HERE / "form_costs_all_cache.json"
if cache.exists():
    allforms = json.loads(cache.read_text())
else:
    have = {f["form"]: f for f in V.forms}
    allforms = list(V.forms)
    ctx_n = {n: t.count("the") for n, t in toks.items()}
    for sh in V.SHAPES:
        for tup in itertools.product(*[V.CON if c == "C" else V.VOW for c in sh]):
            f = "".join(tup)
            if f in have:
                continue
            z = max(zipf_frequency(f, l) for l in LANGS)
            cost = {n: t.count("the " + f) - ctx_n[n] for n, t in toks.items()}
            allforms.append({"form": f, "zipf": z, "cost": cost})
    cache.write_text(json.dumps(allforms))
for cut in [3.0, 4.0, 99]:
    pool = [f for f in allforms if f["zipf"] < cut]
    o = V.order_forms(pool)
    print(f" zipf < {cut}: candidates {len(pool)}; root forms[150:1150] mean tokens "
          + ", ".join(f"{n} {statistics.mean(f['cost'][n] for f in o[150:1150]):.2f}" for n in ["o200k", "claude_legacy", "mistral_sp"]))
    with contextlib.redirect_stdout(io.StringIO()):
        res = V.run(o, "", scen_list=["S4", "S5"], show=False)
    for (k, sc), (nm, tot, _, _) in res.items():
        print(f"   g{k} {sc}: " + ", ".join(f"{n} {tot[n]} ({tot[n] / en[n]:.2f}x en, {tot[n] / te[n]:.2f}x terse)" for n in ["o200k", "claude_legacy"]))

print()
print("e. break-even: tokens per message en_terse vs language S4/S5 (o200k, claude_legacy)")
for n in ["o200k", "claude_legacy"]:
    print(f"  {n}: en_terse {te[n] / 40:.1f}/msg, en {en[n] / 40:.1f}/msg")
