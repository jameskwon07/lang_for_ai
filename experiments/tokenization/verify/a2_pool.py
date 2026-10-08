"""attempt_2: build a pool of space-prefixed lowercase forms, measured on all 7 tokenizers.

Candidates: every o200k / llama4 / cl100k vocab entry of the form ' [a-z]{2,8}', plus all CV/CVC/VC/VCC/CCV strings.
Cost of a form on a tokenizer = tokens of 'the ' + form minus tokens of 'the' (form in mid-sentence after a space).
Word filter: max wordfreq zipf over 11 languages.
Output: verify/a2_pool.json  [{form, costs{tok:n}, total, n_single, zipf_max, zipf_lang}]
"""
import itertools
import json
import re
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from toklib import load_all  # noqa: E402
from wordfreq import zipf_frequency  # noqa: E402

LANGS = ["en", "es", "de", "fr", "it", "pt", "nl", "tr", "id", "pl", "sv"]
OUT = Path(__file__).resolve().parent / "a2_pool.json"


def main():
    toks = load_all()
    cands = set()
    for name in ["o200k", "cl100k", "llama4"]:
        enc = toks[name]._enc
        for i in range(enc.n_vocab):
            try:
                b = enc.decode_single_token_bytes(i)
            except KeyError:
                continue
            s = b.decode("latin-1")
            if re.fullmatch(r" [a-z]{2,8}", s):
                cands.add(s[1:])
    V, C = "aeiou", [c for c in string.ascii_lowercase if c not in "aeiou"]
    for shape in ["CV", "VC", "CVC", "VCC", "CCV", "CVV", "VCV"]:
        pools = [V if ch == "V" else C for ch in shape]
        for t in itertools.product(*pools):
            cands.add("".join(t))
    cands = sorted(cands)
    print("candidates", len(cands), file=sys.stderr)
    base = {n: t.count("the") for n, t in toks.items()}
    rows = []
    for f in cands:
        costs = {n: t.count("the " + f) - base[n] for n, t in toks.items()}
        z = {lg: zipf_frequency(f, lg) for lg in LANGS}
        lg = max(z, key=z.get)
        rows.append({"form": f, "costs": costs, "total": sum(costs.values()),
                     "n_single": sum(1 for v in costs.values() if v == 1),
                     "zipf_max": z[lg], "zipf_lang": lg})
    OUT.write_text(json.dumps(rows))
    ok = [r for r in rows if r["zipf_max"] < 3.0]
    print("zipf<3:", len(ok))
    print("zipf<3 and single on all 7:", sum(1 for r in ok if r["n_single"] == 7))
    print("zipf<3 and single on 6+:", sum(1 for r in ok if r["n_single"] >= 6))
    print("zipf<3 and total<=8:", sum(1 for r in ok if r["total"] <= 8))
    print("zipf<3 and total<=9:", sum(1 for r in ok if r["total"] <= 9))


if __name__ == "__main__":
    main()
