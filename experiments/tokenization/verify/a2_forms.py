"""attempt_2: filter the form pool and order it by token cost.

Excluded forms:
  - max zipf >= 3.0 over 11 languages (the project's non-word pool rule)
  - English dictionary words (web2 + gcide lists from the english-words package, installed in the scratchpad)
  - modern English / tech words missing from those old lists: en zipf >= 2.0 and not a fragment
    (fragment = proper prefix of a more frequent English word that is not just an inflection of the form)
  - code identifiers that a programmer reads directly (blocklist)
  - forms that are not a proper prefix of any word with zipf >= 3.0 in the 11 languages (drops standalone code
    identifiers and library names such as tqdm, rgba, seaborn, which are single tokens but are not word fragments)
  - confusable forms: prefixes of English function words or number words, negative-contraction stems (hasn,
    wouldn), and grammar abbreviations (neg, prob, ...)
Order: number of tokenizers where the form costs more than 1 token, then total tokens over 7, then length.
Output: verify/a2_forms.json [{form, costs, total, n_single, zipf_max, en_zipf}]
"""
import json
import os
import sys
from pathlib import Path

from wordfreq import top_n_list, zipf_frequency

HERE = Path(__file__).resolve().parent
SCRATCH = os.environ.get("A2_PYLIB")
if SCRATCH:
    sys.path.insert(0, SCRATCH)
from english_words import get_english_words_set  # noqa: E402

CODE = set("""py wx cfg cmd ctx idx uid uuid utf json href args argc argv attrs bool boolean dict enum func init impl
kwargs params printf sizeof struct typedef typeof uint onclick foreach readonly retval dtype javax numpy regex async utils
opts ptr rhs lhs cls fmt src tmp str obj num len dst env cpp const var val buf eval exec repl stdin stdout stderr
goog llam lookup logger parser parsed bitmap backend callback endpoint filename datetime iterator datasets debug widget
mutex popup yaml cref akov unset tuple scalar substr cached embed encode append operand opacity indent trunc retry
""".split())
INFL = ("s", "es", "ed", "d", "ing", "er", "ers", "ly", "y")
LANGS = ["en", "es", "de", "fr", "it", "pt", "nl", "tr", "id", "pl", "sv"]
# Words a form must not look like the start of (they would mislead a reader about function words or numbers).
CONFUSE = set("""a an the and or but if then else so because as of at by for from in into on onto to with without about
above below over under between through during before after since until than via per i me my mine you your we us our
they them their he him his she her it its this that these those there here who whom whose which what when where why
how is am are was were be been being have has had do does did will would shall should can could may might must not no
nor yes all any both each every either neither some such only same very too also just never always again still yet
already maybe perhaps probably more most less least zero one two three four five six seven eight nine ten eleven twelve
thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety
hundred thousand million billion first second third fourth fifth sixth seventh eighth ninth tenth half twice none
nothing everything something anything everyone someone""".split())
CONTRACT = set("hasn wouldn couldn shouldn didn doesn isn wasn aren weren hadn mustn needn mightn ain".split())
GRAMMAR_ABBR = set("neg prob prev cond conj rel prog fut perf imp decl quest pl sg num ord pos det adj adv aux nom acc "
                   "gen dat pres pret subj obj ptcp ger inf".split())


def main():
    rows = json.loads((HERE / "a2_pool.json").read_text())
    dict_words = get_english_words_set(["web2"], lower=True) | get_english_words_set(["gcide"], lower=True)
    en_top = [w for w in top_n_list("en", 200000) if w.isalpha()]
    en_z = {}
    prefixes = set()
    for lg in LANGS:
        for w in top_n_list(lg, 80000):
            if w.isalpha() and w.isascii() and zipf_frequency(w, lg) >= 3.0:
                w = w.lower()
                for k in range(2, len(w)):
                    prefixes.add(w[:k])
    out, why = [], {"zipf": 0, "dict": 0, "modern_word": 0, "code": 0, "not_fragment": 0, "confusable": 0}
    for r in rows:
        f = r["form"]
        if r["zipf_max"] >= 3.0:
            why["zipf"] += 1
            continue
        if f in CODE:
            why["code"] += 1
            continue
        if f in dict_words:
            why["dict"] += 1
            continue
        ez = zipf_frequency(f, "en")
        if ez >= 2.0:
            longer = [w for w in en_top[:60000] if w.startswith(f) and w != f and w[len(f):] not in INFL]
            frag = any(zipf_frequency(w, "en") >= ez + 0.5 for w in longer[:50])
            if not frag:
                why["modern_word"] += 1
                continue
        if f not in prefixes:
            why["not_fragment"] += 1
            continue
        if f in CONTRACT or f in GRAMMAR_ABBR or any(w.startswith(f) for w in CONFUSE):
            why["confusable"] += 1
            continue
        r["en_zipf"] = ez
        out.append(r)
    out.sort(key=lambda r: (7 - r["n_single"], r["total"], len(r["form"]), r["form"]))
    (HERE / "a2_forms.json").write_text(json.dumps(out))
    print("excluded", why, "kept", len(out))
    names = list(out[0]["costs"].keys())
    for k in [75, 300, 640, 1000, 1500, 1800, 2000]:
        sub = out[:k]
        print(k, {n: round(sum(r["costs"][n] for r in sub[-100:]) / 100, 2) for n in names},
              "| n_single7 in prefix:", sum(1 for r in sub if r["n_single"] == 7))


if __name__ == "__main__":
    main()
