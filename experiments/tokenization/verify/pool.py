"""Attempt 1 helper: build the largest pool of space-prefixed letter-only forms
that are cheap in all 7 tokenizers and pass the word filter (max zipf < 3.0, 11 languages).

Candidates = every vocabulary entry of every tokenizer that is a leading space + 2..8 ASCII letters,
plus its lowercase variant. Cost per tokenizer is measured in context: count("the " + f) - count("the").
Output: verify/pool_attempt_1.json (sorted by mean cost, then max cost, then zipf).
Usage (from experiments/tokenization): python3 verify/pool.py
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from toklib import load_all  # noqa: E402
from wordfreq import zipf_frequency  # noqa: E402

LANGS = ["en", "es", "de", "fr", "it", "pt", "nl", "tr", "id", "pl", "sv"]
PAT = re.compile(r"^ [A-Za-z]{2,14}$")


def vocab_strings(t) -> set[str]:
    out = set()
    if hasattr(t, "_enc"):
        for b in t._enc._mergeable_ranks:
            try:
                s = b.decode("ascii")
            except UnicodeDecodeError:
                continue
            out.add(s)
    elif hasattr(t, "_tok"):
        inv = {v: k for k, v in t._byte_of.items()}  # noqa: F841
        for tokstr in t._tok.get_vocab():
            try:
                s = bytes(t._byte_of[ch] for ch in tokstr).decode("ascii")
            except (KeyError, UnicodeDecodeError):
                continue
            out.add(s)
    else:
        sp = t._sp
        for i in range(sp.get_piece_size()):
            out.add(sp.id_to_piece(i).replace("▁", " "))
    return out


def main() -> None:
    toks = load_all()
    cands: set[str] = set()
    for t in toks.values():
        for s in vocab_strings(t):
            if PAT.match(s):
                cands.add(s[1:])
                cands.add(s[1:].lower())
    print("raw candidates", len(cands))
    base = {n: t.count("the") for n, t in toks.items()}
    rows = []
    for f in sorted(cands):
        z = max(zipf_frequency(f.lower(), lang) for lang in LANGS)
        if z >= 3.0:
            continue
        cost = {n: t.count(f"the {f}") - base[n] for n, t in toks.items()}
        bare = {n: t.count(f) for n, t in toks.items()}
        rows.append({"form": f, "zipf": round(z, 2), "cost": cost, "bare": bare,
                     "mean": statistics.mean(cost.values()), "max": max(cost.values()),
                     "n_single": sum(1 for v in cost.values() if v == 1)})
    rows.sort(key=lambda r: (r["mean"], r["max"], statistics.mean(r["bare"].values()), r["zipf"], len(r["form"]), r["form"]))
    (HERE / "pool_attempt_1.json").write_text(json.dumps(rows, indent=0))
    lower = [r for r in rows if r["form"].islower()]
    for label, rs in (("all", rows), ("lowercase", lower)):
        all7 = [r for r in rs if r["n_single"] == 7]
        print(label, "filtered", len(rs), "single in all 7:", len(all7),
              "single in >=6:", sum(1 for r in rs if r["n_single"] >= 6),
              "max<=2 all7:", sum(1 for r in rs if r["max"] <= 2))
        for n in toks:
            print("   ", n, "single:", sum(1 for r in rs if r["cost"][n] == 1))
    print("first 80 lowercase all-7:", [r["form"] for r in lower if r["n_single"] == 7][:80])


if __name__ == "__main__":
    main()
