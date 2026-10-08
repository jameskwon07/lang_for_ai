"""Shape-free lead-space pool for 6 tokenizers (without mistral_sp) and for claude_legacy alone, confirmed in context."""
import contextlib, io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
with contextlib.redirect_stdout(io.StringIO()):
    import v_inventory as I
from collections import Counter

def single(names, s, ctx="the"):
    for n in names:
        t = I.toks[n]
        if t.count(ctx + s) - t.count(ctx) != 1:
            return False
    return True

for label, names in [("6 without mistral_sp", [n for n in I.toks if n != "mistral_sp"]),
                     ("claude_legacy alone", ["claude_legacy"]), ("o200k alone", ["o200k"])]:
    cand = set.intersection(*[{s for s in I.V[n] if I.LEAD.match(s)} for n in names])
    conf = [s for s in cand if single(names, s)]
    lt3 = [s.strip() for s in conf if I.maxz(s.strip()) < 3.0]
    cons = [w for w in lt3 if w[0] not in I.VOW]
    frag = sum(w in I.pre_en for w in lt3) / len(lt3)
    print(f"{label}: lead-space single {len(conf)}, max zipf<3 {len(lt3)} (consonant-initial {len(cons)}), "
          f"English-prefix share {frag:.0%}")
