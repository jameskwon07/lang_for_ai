"""attempt_2: general English content-lemma frequency ranking (wordfreq), used to place concepts in a general lexicon.

Rank = position among English content lemmas sorted by the wordfreq frequency of their most frequent form.
Two-pass folding: an inflected form (-s/-es/-ies/-ed/-ied/-ing, plus a table of irregular forms) is folded into
its stem when the stem occurs anywhere in the list. Function words are removed.
in_dict marks lemmas found in the web2/gcide English word lists (lowercase entries), which removes names, places,
brands and slang; a2_build.py keeps only in_dict lemmas (or domain-block terms) in the general block.
This is computed without looking at the corpus.
Output: verify/a2_rank.json {lemma: [rank, in_dict]}
"""
import json
import os
import re
import sys
from pathlib import Path

from wordfreq import top_n_list

SCRATCH = os.environ.get("A2_PYLIB")
if SCRATCH:
    sys.path.insert(0, SCRATCH)
from english_words import get_english_words_set  # noqa: E402

OUT = Path(__file__).resolve().parent / "a2_rank.json"

FUNCTION = set("""
a an the and or but if then else so because as of at by for from in into on onto to with without about above below over under
between through during before after since until than via per
i me my mine myself you your yours yourself he him his himself she her hers herself it its itself we us our ours ourselves
they them their theirs themselves this that these those there here who whom whose which what when where why how
is am are was were be been being have has had having do does did doing will would shall should can could may might must
not no nor yes all any both each every either neither some such only same very too also just
oh ok okay yeah hey hi hello lol im dont didnt doesnt isnt wasnt cant wont thats youre ive id ill hes shes theyre weve
s t d ll m re ve
""".split())

# Lexicalized -ing/-ed/-s words kept as their own lemmas. General list, not corpus-specific.
KEEP = set("""meeting missing building training setting morning evening feeling beginning wedding ceiling clothing painting
opening funding finding ranking heading listing logging billing pricing rating saying spending interesting amazing exciting
boring existing following remaining ongoing outstanding advanced limited based related fixed united married
hearing housing parking shopping marketing thing during nothing everything something anything ring king spring string
wing sing bring news means goods glasses arms physics series species left""".split())

IRREG = dict(x.split(":") for x in """said:say made:make got:get went:go came:come took:take saw:see knew:know
thought:think found:find told:tell felt:feel kept:keep began:begin brought:bring bought:buy built:build caught:catch
chose:choose drew:draw drove:drive ate:eat fell:fall fought:fight flew:fly forgot:forget gave:give grew:grow held:hold
hid:hide laid:lay led:lead lent:lend lost:lose meant:mean met:meet paid:pay ran:run rang:ring rose:rise sang:sing sat:sit
sent:send shook:shake shot:shoot slept:sleep sold:sell spent:spend spoke:speak stood:stand stole:steal struck:strike
swore:swear taught:teach tore:tear threw:throw understood:understand woke:wake won:win wore:wear wrote:write done:do
gone:go seen:see known:know taken:take given:give written:write spoken:speak eaten:eat fallen:fall forgotten:forget
gotten:get hidden:hide ridden:ride risen:rise shown:show stolen:steal thrown:throw worn:wear broken:break chosen:choose
driven:drive frozen:freeze beaten:beat bitten:bite became:become begun:begin drunk:drink sung:sing children:child
men:man women:woman feet:foot teeth:tooth mice:mouse lives:life wives:wife knives:knife better:good best:good
worse:bad worst:bad""".split())


def stems_of(w):
    st = []
    if w.endswith("ies"):
        st.append(w[:-3] + "y")
    if w.endswith("es"):
        st.append(w[:-2])
    if w.endswith("s") and not w.endswith("ss"):
        st.append(w[:-1])
    if w.endswith("ied"):
        st.append(w[:-3] + "y")
    if w.endswith("ed") and not w.endswith("eed") and len(w) >= 5:
        st += [w[:-2], w[:-1]]
        if w[-3] == w[-4]:
            st.append(w[:-3])
    if w.endswith("ing") and len(w) >= 6:
        st += [w[:-3], w[:-3] + "e"]
        if w[-4] == w[-5]:
            st.append(w[:-4])
    return [s for s in st if len(s) >= 2]


def main():
    words = [w for w in top_n_list("en", 60000) if re.fullmatch(r"[a-z]{2,}", w) and w not in FUNCTION]
    wset = set(words)
    lemma_of = {}
    for w in words:
        if w in KEEP:
            lemma_of[w] = w
        elif w in IRREG and IRREG[w] in wset | FUNCTION:
            lemma_of[w] = IRREG[w]
        else:
            st = [s for s in stems_of(w) if s in wset]
            lemma_of[w] = st[0] if st else w
    ranked, seen = [], set()
    for w in words:  # frequency order; a lemma takes the position of its most frequent form
        lem = lemma_of[w]
        if lem in FUNCTION or lem in seen:
            continue
        seen.add(lem)
        ranked.append(lem)
    web = get_english_words_set(["web2"], lower=False) | get_english_words_set(["gcide"], lower=False)
    low = {w for w in web if w.islower()}
    OUT.write_text(json.dumps({w: [i, w in low] for i, w in enumerate(ranked)}))
    print("lemmas", len(ranked), "in_dict among first 2500:", sum(1 for w in ranked[:2500] if w in low))
    print(ranked[:80])


if __name__ == "__main__":
    main()
