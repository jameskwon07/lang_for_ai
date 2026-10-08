"""Independent check of claim C1 via vocabulary intersection (shape-free upper bound).

Instead of enumerating letter shapes, take every vocabulary entry of each tokenizer that is
' ' + [a-z]+ (leading-space spelling) or [a-z]+ (bare spelling), intersect across the 7 tokenizers,
confirm in context that the form really comes out as one token, then apply the 11-language zipf filter.
This bounds what ANY shape can deliver for single-token lowercase forms.

Also: fragment test restricted to English words, and a recount of a few inventory.json numbers.

Run from experiments/tokenization:  python3 verify/v_inventory.py
"""
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from toklib import load_all, TiktokenTok, HFTok, SentencePieceTok  # noqa: E402
from wordfreq import zipf_frequency, get_frequency_dict  # noqa: E402

toks = load_all()
LANGS = ["en", "es", "de", "fr", "it", "pt", "nl", "tr", "id", "pl", "sv"]
VOW = set("aeiou")


def vocab_strings(t):
    out = set()
    if isinstance(t, TiktokenTok):
        for b in t._enc._mergeable_ranks:
            try:
                out.add(b.decode("ascii"))
            except UnicodeDecodeError:
                pass
    elif isinstance(t, HFTok):
        for s in t._tok.get_vocab():
            try:
                out.add(bytes(t._byte_of[c] for c in s).decode("ascii"))
            except (KeyError, UnicodeDecodeError):
                pass
    elif isinstance(t, SentencePieceTok):
        for i in range(t._sp.get_piece_size()):
            out.add(t._sp.id_to_piece(i).replace("▁", " "))
    return out


V = {n: vocab_strings(t) for n, t in toks.items()}
LEAD = re.compile(r"^ [a-z]+$")
BARE = re.compile(r"^[a-z]+$")
LEADCAP = re.compile(r"^ [A-Z][a-z]*$")


def ctx_cost(t, ctx, s):
    return t.count(ctx + s) - t.count(ctx)


def single_all7(s, ctx):
    # context method as in inventory.py, but also guard against merges with the context via pieces
    for n, t in toks.items():
        p = t.pieces(ctx + s)
        # find pieces after the context
        pos, after = 0, []
        for piece in p:
            start = pos
            pos += len(piece)
            if start < len(ctx) < pos:
                return False
            if start >= len(ctx) and piece:
                after.append(piece)
        if len(after) != 1:
            return False
    return True


zcache = {}


def maxz(w):
    w = w.lower()
    if w not in zcache:
        zcache[w] = max(zipf_frequency(w, l) for l in LANGS)
    return zcache[w]


results = {}
for label, rx, ctx, strip in [("lead ' kat'", LEAD, "the", True), ("bare 'kat'", BARE, "1", False),
                              ("lead-cap ' Kat'", LEADCAP, "the", True)]:
    cand = set.intersection(*[{s for s in V[n] if rx.match(s)} for n in toks])
    conf = sorted(s for s in cand if single_all7(s, ctx))
    words = [s.strip() for s in conf]
    lt3 = [w for w in words if maxz(w) < 3.0]
    lt2 = [w for w in words if maxz(w) < 2.0]
    c_init = [w for w in lt3 if w[0].lower() not in VOW]
    results[label] = lt3
    lens = Counter(len(w) for w in lt3)
    print(f"{label}: in all 7 vocabularies {len(cand)}, confirmed single in context {len(conf)}, "
          f"max zipf<3: {len(lt3)} (consonant-initial {len(c_init)}, vowel-initial {len(lt3) - len(c_init)}), "
          f"<2: {len(lt2)}; lengths of <3 forms {dict(sorted(lens.items()))}")
    # vocab-intersection sizes excluding mistral_sp / claude only
    no_sp = set.intersection(*[{s for s in V[n] if rx.match(s)} for n in toks if n != "mistral_sp"])
    print(f"   (6 tokenizers without mistral_sp: vocab intersection {len(no_sp)}, of which max zipf<3: "
          f"{sum(1 for s in no_sp if maxz(s.strip()) < 3.0)} before context confirmation)")

# Inventory claims "pooled lead-space root pool, all 7, zipf<3 = 205" (consonant-initial shapes only, lengths 2-5)
lt3_lead = results["lead ' kat'"]
shape = lambda w: "".join("V" if c in VOW else "C" for c in w)
inv_shapes = {"CV", "CVV", "CCV", "CVC", "CVCV", "CCVC", "CVCC", "CVCVC"}
in_inv = [w for w in lt3_lead if shape(w) in inv_shapes]
print(f"lead-space all7 zipf<3 forms whose shape is one of inventory.py's 8 root shapes: {len(in_inv)} (inventory.md: 205)")
other = Counter(shape(w) for w in lt3_lead if shape(w) not in inv_shapes and w[0] not in VOW)
print("consonant-initial forms in other shapes:", sum(other.values()), other.most_common(12))
print("examples, other shapes:", [w for w in lt3_lead if shape(w) not in inv_shapes][:60])

# Fragment test, English only vs 11 languages
print()
en_words = {w for w, f in get_frequency_dict("en").items() if f >= 1e-6 and w.isalpha()}
all_words = set()
for l in LANGS:
    all_words |= {w.lower() for w, f in get_frequency_dict(l).items() if f >= 1e-6}


def prefix_set(words, maxlen=8):
    s = set()
    for w in words:
        for k in range(1, min(maxlen, len(w) - 1) + 1):
            s.add(w[:k])
    return s


pre_en, pre_all = prefix_set(en_words), prefix_set(all_words)
rng = random.Random(7)
# control: random lowercase strings with the same length and initial-letter class, zipf<3, not single token in o200k
o = toks["o200k"]
ctrl = []
letters = "abcdefghijklmnopqrstuvwxyz"
for w in lt3_lead:
    while True:
        cand = "".join(rng.choice(letters) for _ in range(len(w)))
        if maxz(cand) < 3.0 and ctx_cost(o, "the", " " + cand) > 1:
            ctrl.append(cand)
            break
for name, pool in [("all7 lead-space zipf<3", lt3_lead), ("random control (same lengths)", ctrl)]:
    print(f"{name}: n={len(pool)}, proper prefix of an English zipf>=3 word: "
          f"{sum(w in pre_en for w in pool) / len(pool):.0%}; of an 11-language zipf>=3 word: "
          f"{sum(w in pre_all for w in pool) / len(pool):.0%}")
nonfrag = [w for w in lt3_lead if w not in pre_en]
print("all7 lead-space zipf<3 forms that are NOT an English-word prefix:", len(nonfrag), nonfrag[:80])

# recount a few inventory.json numbers directly
inv = json.loads((ROOT / "results" / "inventory.json").read_text())
for shp, var in [("CVC", "space"), ("CVCC", "space"), ("CVC", "bare"), ("VCVC", "bare")]:
    lst = [f for f, z in inv["lists"][shp][var]["all7_lt3"]]
    ctx = "the" if var == "space" else "1"
    pre = " " if var == "space" else ""
    ok = sum(1 for f in lst if single_all7(pre + f, ctx) and maxz(f) < 3.0)
    print(f"inventory.json {shp} {var} all7_lt3: listed {len(lst)}, re-verified {ok}")
# completeness check for CVC space: enumerate all 2205 directly
C = "bcdfghjklmnpqrstvwxyz"
mine = [a + v + b for a in C for v in "aeiou" for b in C if single_all7(" " + a + v + b, "the") and maxz(a + v + b) < 3.0]
print("CVC ' kat' all7 & zipf<3 by full enumeration:", len(mine))
