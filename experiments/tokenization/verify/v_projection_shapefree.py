"""Bias check for C3: projection.py only draws forms from 6 shapes (CV CVC CCV CVCC CCVC CVCV).
Here the 657 forms that are single tokens with a leading space in all 7 tokenizers (any shape, zipf<3, from
v_inventory.py) go first, followed by projection's own ordered list. Same scenarios and lexicon rule."""
import contextlib, io, sys, statistics
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
with contextlib.redirect_stdout(io.StringIO()):
    import v_projection as V
    import v_inventory as I
toks = V.toks
pool = I.results["lead ' kat'"]
ctx_n = {n: t.count("the") for n, t in toks.items()}
extra = [{"form": w, "zipf": I.maxz(w), "cost": {n: t.count("the " + w) - ctx_n[n] for n, t in toks.items()}} for w in pool]
have = {f["form"] for f in extra}
ordered = V.order_forms(extra) + [f for f in V.order_forms(V.forms) if f["form"] not in have]
print("root forms[150:1150] mean tokens:", {n: round(statistics.mean(f["cost"][n] for f in ordered[150:1150]), 3) for n in V.NAMES})
V.run(ordered, "shape-free all-7 pool first", scen_list=["S1", "S4", "S5"])
