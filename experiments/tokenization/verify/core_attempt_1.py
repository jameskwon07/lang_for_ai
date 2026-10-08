"""Attempt 1: general core vocabulary = most frequent English content lemmas (wordfreq), function words removed.

Lemmas are merged naively (plural, -ed, -ing, -ly, -er/-est variants map to a base that is itself in the list).
Frequency of a lemma = sum of the frequencies of the merged forms. Proper names are not removed exhaustively.
"""
from __future__ import annotations

from wordfreq import top_n_list, zipf_frequency

# function words / items the grammar section covers (so they are not core roots)
STOP = set("""
a an the of to in and or but is are was were be been being am i you he she it we they me him her us them my your his
its our their mine yours hers ours theirs this that these those not no do does did done doing have has had having
will would can could should may might must shall for with on at by from as if then than so what which who whom whose
where when why how all any some each every other another only more most less least too very also now here there just
about after before until again already still yet never ever up down out over off into onto upon through between
because while although though whether either neither both nor such same s t d ll m re ve don didn doesn isn aren
wasn weren won wouldn couldn shouldn hasn haven hadn let lets yes ok okay oh hey hi hello please thanks thank im ive
youre thats dont cant wont theres whats lol gonna wanna yeah first last one two three four five six seven eight
nine ten hundred thousand million percent per get got also even much many really well back
""".split())
# a few very frequent proper names / places that are not general concepts
NAMES = set("""
john york america american trump obama london paul david michael james george mike chris peter mark tom california
texas florida china chinese india canada uk usa england english british france french germany german japan japanese
europe european australia mr mrs ms dr ne th com br tim liv stat chang fir fil jon sid ty ex ed mid jack thomas
richard louis smith chicago paris frank rose van ad fuck shit bitch dude damn ass lmao omg tho gon ya na wo ur cuz pm
am jan feb mar apr jun jul aug sep sept oct nov dec monday tuesday wednesday thursday friday saturday sunday jesus god christ christmas facebook twitter google youtube instagram apple
microsoft amazon iphone android windows bill_ jr st co inc vs etc
""".split())


def build_core(n_core: int, scan: int = 20000) -> list[tuple[str, float]]:
    words = [w for w in top_n_list("en", scan) if w.isalpha() and w.isascii() and len(w) >= 2]
    words = [w for w in words if w not in STOP and w not in NAMES]
    wset = set(words)
    freq = {w: 10 ** zipf_frequency(w, "en") for w in words}

    no_merge = {"likely", "early", "family", "supply", "rally", "reply", "apply", "only", "holy", "ugly", "bully",
                "belly", "jelly", "lately", "hardly", "nearly", "shortly", "barely", "badly", "fairly"}

    def base_of(w: str) -> str | None:
        if w in no_merge:
            return None
        cands = []
        if w.endswith("ies"):
            cands.append(w[:-3] + "y")
        if w.endswith("es"):
            cands.append(w[:-2])
        if w.endswith("s") and not w.endswith("ss"):
            cands.append(w[:-1])
        if w.endswith("ied"):
            cands.append(w[:-3] + "y")
        if w.endswith("ed"):
            cands += [w[:-2], w[:-1]]
            if len(w) > 4 and w[-3] == w[-4]:
                cands.append(w[:-3])
        if w.endswith("ing"):
            cands += [w[:-3], w[:-3] + "e"]
            if len(w) > 5 and w[-4] == w[-5]:
                cands.append(w[:-4])
        if w.endswith("ly"):
            cands.append(w[:-2])
            if w.endswith("ily"):
                cands.append(w[:-3] + "y")
        for c in cands:
            # guard against bogus bases (reply->rep, need->ne, apply->app):
            # -ly needs a base of >= 4 letters; other suffixes need word >= 5 and base >= 3 letters
            ok = len(c) >= 4 if w.endswith("ly") else (len(w) >= 5 and len(c) >= 3)
            if c != w and c in wset and ok:
                return c
        return None

    lemma_freq: dict[str, float] = {}
    for w in words:
        b = base_of(w)
        # follow one more step (e.g. 'studies' -> 'study'; 'workings' -> 'working' -> 'work')
        if b is not None:
            b2 = base_of(b)
            if b2 is not None:
                b = b2
        key = b or w
        lemma_freq[key] = lemma_freq.get(key, 0.0) + freq[w]
    ranked = sorted(lemma_freq.items(), key=lambda kv: -kv[1])
    import math
    return [(w, round(math.log10(f), 3)) for w, f in ranked[:n_core]]


if __name__ == "__main__":
    core = build_core(1500)
    print(len(core))
    print(" ".join(w for w, _ in core[:300]))
    print("...")
    print(" ".join(w for w, _ in core[1200:1500]))
    print("zipf at 1000, 1200, 1500:", core[999][1], core[1199][1], core[-1][1])
