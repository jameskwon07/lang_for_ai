"""Independent check of claim C2 (W2 spaced -> ~1 token per morpheme; W1 glued misaligns).

Own message generator (uniform word lengths, different RNG and structure from alignment.py) and own
boundary metric computed from piece character offsets. Three lexicons:
  A. alignment.py's token_picked pool (59 CVC roots, 34 VC affixes) -- reproduces the claim's condition
  B. a realistic lexicon: projection.py-style ordered forms (150 closed + 1,000 roots, zipf < 3)
  C. the 205 forms that are single tokens with a leading space in all 7 tokenizers (inventory pool) + 100 affixes

Run from experiments/tokenization:  python3 verify/v_alignment.py
"""
import json
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from toklib import load_all  # noqa: E402

toks = load_all()
AL = json.loads((ROOT / "results" / "alignment.json").read_text())
roots_A = AL["pools"]["token_picked_roots"]
aff_A = AL["pools"]["token_picked_affixes"]

forms = json.loads((HERE / "form_costs_cache.json").read_text())  # written by v_projection.py
forms.sort(key=lambda r: (statistics.mean(r["cost"].values()), max(r["cost"].values()), r["zipf"], len(r["form"]), r["form"]))
closed_B = [f["form"] for f in forms[:150]]
roots_B = [f["form"] for f in forms[150:1150]]


def gen_messages(rng, roots, affixes, n=200):
    """message = 3-8 words; word = 1 root (15%: 2 roots) + 0-3 affixes chosen uniformly."""
    msgs = []
    for _ in range(n):
        words = []
        for _ in range(rng.randint(3, 8)):
            w = [("R", rng.choice(roots)) for _ in range(2 if rng.random() < 0.15 else 1)]
            w += [("A", a) for a in rng.sample(affixes, rng.choice([0, 1, 1, 2, 3]))]
            words.append(w)
        msgs.append(words)
    return msgs


def render(words, spaced):
    text, starts = "", []
    for w in words:
        for _, f in w:
            if spaced and text:
                text += " "
            starts.append(len(text) if not (spaced and len(text) > 0) else len(text) - 1)
            text += f
    return text, starts


def metrics(tok, msgs, spaced):
    T = M = hit = mb = tb = 0
    for words in msgs:
        text, starts = render(words, spaced)
        pieces = tok.pieces(text)
        assert "".join(pieces) == text, (tok.name, text, pieces)
        b, pos = set(), 0
        for p in pieces:
            pos += len(p)
            b.add(pos)
        inner = b - {len(text)}
        T += len(pieces)
        M += len(starts)
        mbs = set(starts[1:])
        mb += len(mbs)
        hit += len(mbs & inner)
        tb += len(inner - {0})
    return T / M, hit / mb, hit / tb


rng = random.Random(4242)
setups = {
    "A token_picked (59 roots/34 affixes)": (roots_A, aff_A),
    "B realistic (1000 roots from forms[150:1150], 150 closed)": (roots_B, closed_B),
}
# C: inventory's all-7 single-token, zipf<3 leading-space pool, from inventory.json if present
inv_path = ROOT / "results" / "inventory.json"
if inv_path.exists():
    inv = json.loads(inv_path.read_text())
    pool = []
    for shape in ["CV", "CVV", "CCV", "CVC", "CVCV", "CCVC", "CVCC", "CVCVC"]:
        pool += [f for f, z in inv["lists"][shape]["space"]["all7_lt3"]]
    setups[f"C inventory all7 lead-space pool ({len(pool)} roots) + 150 closed"] = (pool, closed_B)

for label, (R, A) in setups.items():
    msgs = gen_messages(rng, R, A)
    print(label)
    for name, t in toks.items():
        w2 = metrics(t, msgs, True)
        w1 = metrics(t, msgs, False)
        print(f"  {name:15} W2 tpm {w2[0]:.3f} R {w2[1]:.3f} P {w2[2]:.3f} | W1 tpm {w1[0]:.3f} R {w1[1]:.3f} P {w1[2]:.3f}")
