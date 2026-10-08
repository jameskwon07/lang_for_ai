"""Independent recount of the E3 baseline (claim C5) and of the per-message values projection.py reads.

Run from experiments/tokenization:  python3 verify/v_baseline.py
"""
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from toklib import load_all  # noqa: E402

corpus = json.loads((ROOT / "corpus" / "ai_messages.json").read_text())
base = json.loads((ROOT / "results" / "baseline.json").read_text())
toks = load_all()
V = ["en", "en_terse", "ko", "json"]

mismatch = []
totals = {n: {v: 0 for v in V} for n in toks}
for m in corpus:
    for n, t in toks.items():
        for v in V:
            c = t.count(m[v])
            totals[n][v] += c
            if base["per_message"][m["id"]][n][v] != c:
                mismatch.append((m["id"], n, v, base["per_message"][m["id"]][n][v], c))

print("per-message mismatches vs baseline.json:", len(mismatch), mismatch[:10])
print("ids in baseline.json per_message == corpus ids:", sorted(base["per_message"]) == sorted(m["id"] for m in corpus))
print()
print(f"{'tok':15} {'en':>5} {'terse':>6} {'ko':>5} {'json':>5}  terse/en ko/en json/en")
ratios = {v: [] for v in V}
for n in toks:
    T = totals[n]
    r = {v: T[v] / T["en"] for v in V}
    for v in V:
        ratios[v].append(r[v])
    print(f"{n:15} {T['en']:5} {T['en_terse']:6} {T['ko']:5} {T['json']:5}  {r['en_terse']:.3f}   {r['ko']:.3f} {r['json']:.3f}")
print("mean over 7:", {v: round(statistics.mean(ratios[v]), 3) for v in V})
print("min/max over 7:", {v: (round(min(ratios[v]), 3), round(max(ratios[v]), 3)) for v in V})

# Per-message ratio view (does the 'about 1.00x' JSON hold message by message?)
for n in ["o200k", "claude_legacy"]:
    t = toks[n]
    js = [t.count(m["json"]) / t.count(m["en"]) for m in corpus]
    te = [t.count(m["en_terse"]) / t.count(m["en"]) for m in corpus]
    print(n, "json/en per-msg median %.2f min %.2f max %.2f; terse/en median %.2f min %.2f max %.2f" % (
        statistics.median(js), min(js), max(js), statistics.median(te), min(te), max(te)))

# Sensitivity: what if the messages are prefixed by a space (mid-conversation position)?
print()
for n, t in toks.items():
    a = sum(t.count(m["en"]) for m in corpus)
    b = sum(t.count(" " + m["en"]) for m in corpus)
    c = sum(t.count("\n" + m["en"]) for m in corpus)
    print(f"{n:15} en total as-is {a}, with leading space {b}, with leading newline {c}")
