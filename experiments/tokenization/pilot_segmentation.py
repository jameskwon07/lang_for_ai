"""Pilot: how accurately an LLM reads and writes a toy language, depending on the spelling.

The same toy language (24 CVC roots, 12 VC affixes) is written in four spellings.
LLM subjects get only the spec and are asked to do (1) sentence analysis (morpheme segmentation + gloss)
and (2) gloss → sentence generation.

Spellings
- nospace    : all morphemes glued (no spaces)            katenmirob
- spaced     : one space between morphemes                kat en mir ob
- wordspaced : one space between words (root + affixes)   katen mirob
- camel      : no spaces, each morpheme capitalized       KatEnMirOb

Usage
    python3 pilot_segmentation.py materials OUT_DIR   # save subject materials (without answers) and the answer key separately
    python3 pilot_segmentation.py score OUT_DIR ANSWERS.json   # score answers
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from wordfreq import zipf_frequency

SEED = 20261007
VOWELS = "aeiou"
CONSONANTS = "bdfgklmnprstvz"
WORD_LANGS = ["en", "es", "de", "fr", "it", "pt", "nl", "tr", "id"]

NOUNS = ["user", "file", "server", "task", "error", "tool", "result", "agent", "message", "plan"]
VERBS = ["send", "read", "write", "find", "fix", "run", "check", "delete"]
ADJS = ["new", "old", "large", "small", "wrong", "ready"]
# Experiment stimuli: the Korean strings in the AFFIXES descriptions, DESIGN_RULES and spec_text
# build the spec that was given to the subjects in Korean. They are kept verbatim; do not translate them.
AFFIXES = {
    "AGT": "행위자 (누가)",
    "PAT": "대상 (무엇을)",
    "REC": "받는 쪽 (누구에게)",
    "INS": "도구 (무엇으로)",
    "SRC": "출처 (어디에서)",
    "PL": "복수",
    "PST": "과거",
    "FUT": "미래",
    "NEG": "부정",
    "Q": "의문",
    "CERT": "확실함 (직접 확인)",
    "INFR": "추론함",
}
ROLES = ["AGT", "PAT", "REC", "INS", "SRC"]
DESIGNS = ["nospace", "spaced", "wordspaced", "camel"]
N_PARSE, N_GENERATE = 20, 20


def max_zipf(form: str) -> float:
    return max(zipf_frequency(form, lang) for lang in WORD_LANGS)


def build_lexicon(rng: random.Random) -> tuple[dict[str, str], dict[str, str]]:
    """Meaning → form. Forms that overlap with common words in several languages are dropped."""
    roots = [c1 + v + c2 for c1 in CONSONANTS for v in VOWELS for c2 in CONSONANTS]
    roots = [r for r in roots if max_zipf(r) < 3.0]
    rng.shuffle(roots)
    root_of = dict(zip(NOUNS + VERBS + ADJS, roots))
    affixes = sorted((v + c for v in VOWELS for c in CONSONANTS), key=lambda f: (max_zipf(f), f))[:30]
    rng.shuffle(affixes)
    affix_of = dict(zip(AFFIXES, affixes))
    return root_of, affix_of


def random_sentence(rng: random.Random) -> list[list[str]]:
    """A list of words. Each word is a list of meaning names (e.g. ['send', 'PST', 'CERT'])."""
    pred = [rng.choice(VERBS)]
    if rng.random() < 0.6:
        pred.append(rng.choice(["PST", "FUT"]))
    if rng.random() < 0.25:
        pred.append("NEG")
    pred.append(rng.choice(["CERT", "INFR"]))
    if rng.random() < 0.2:
        pred.append("Q")
    words = [pred]
    for role in sorted(rng.sample(ROLES, rng.randint(1, 4)), key=ROLES.index):
        word = [rng.choice(NOUNS)]
        if rng.random() < 0.35:
            word.append(rng.choice(ADJS))
        if rng.random() < 0.3:
            word.append("PL")
        word.append(role)
        words.append(word)
    return words


def render(words: list[list[str]], design: str, root_of: dict, affix_of: dict) -> str:
    forms = [[root_of.get(m) or affix_of[m] for m in w] for w in words]
    if design == "nospace":
        return "".join("".join(w) for w in forms)
    if design == "spaced":
        return " ".join(m for w in forms for m in w)
    if design == "wordspaced":
        return " ".join("".join(w) for w in forms)
    if design == "camel":
        return "".join(m.capitalize() for w in forms for m in w)
    raise ValueError(design)


def gloss(words: list[list[str]]) -> str:
    return " ".join("-".join(w) for w in words)


DESIGN_RULES = {
    "nospace": "형태소를 모두 띄어쓰기 없이 붙여 쓴다. 어근은 항상 자음-모음-자음 3글자, 접사는 항상 모음-자음 2글자다. "
               "따라서 다음 글자가 자음이면 어근 3글자를, 모음이면 접사 2글자를 읽으면 된다.",
    "spaced": "형태소마다 공백 하나로 띄어 쓴다.",
    "wordspaced": "단어(어근과 그 뒤에 붙는 접사들)마다 공백 하나로 띄어 쓰고, 단어 안의 형태소는 붙여 쓴다.",
    "camel": "띄어쓰기 없이 쓰되, 모든 형태소의 첫 글자를 대문자로 쓴다.",
}


def spec_text(design: str, root_of: dict, affix_of: dict, rng: random.Random) -> str:
    lines = ["# 장난감 언어 사양", "", "## 어근"]
    lines += [f"- {form} = {meaning} ({'명사' if meaning in NOUNS else '동사' if meaning in VERBS else '형용사'})"
              for meaning, form in sorted(root_of.items(), key=lambda kv: kv[1])]
    lines += ["", "## 접사 (뜻풀이에서는 대문자 이름을 쓴다)"]
    lines += [f"- {form} = {name}: {AFFIXES[name]}" for name, form in sorted(affix_of.items(), key=lambda kv: kv[1])]
    lines += [
        "", "## 문법",
        "- 문장은 술어 단어 하나로 시작하고, 그 뒤에 논항 단어가 1~4개 온다.",
        "- 술어 단어 = 동사 어근 + [PST 또는 FUT] + [NEG] + (CERT 또는 INFR 중 하나, 필수) + [Q]",
        "- 논항 단어 = 명사 어근 + [형용사 어근] + [PL] + 역할 접사(AGT, PAT, REC, INS, SRC 중 하나, 필수)",
        "- 논항은 AGT, PAT, REC, INS, SRC 순서로 온다.",
        "- 형용사 어근은 명사 어근 바로 뒤에 붙어 같은 단어가 된다.",
        "", "## 표기", f"- {DESIGN_RULES[design]}",
        "", "## 뜻풀이 형식",
        "- 단어 안의 형태소 뜻은 하이픈(-)으로 잇고, 단어 사이는 공백 하나로 띄운다.",
        "- 어근은 영어 뜻(user, send, new …), 접사는 대문자 이름(PST, AGT …)으로 쓴다.",
        "", "## 예시",
    ]
    for _ in range(2):
        words = random_sentence(rng)
        lines.append(f"- 문장: {render(words, design, root_of, affix_of)}")
        lines.append(f"  뜻풀이: {gloss(words)}")
    return "\n".join(lines)


def make(out_dir: Path) -> None:
    rng = random.Random(SEED)
    root_of, affix_of = build_lexicon(rng)
    sentences = [random_sentence(rng) for _ in range(N_PARSE + N_GENERATE)]
    materials, gold = {}, {"lexicon": {"roots": root_of, "affixes": affix_of}, "designs": {}}
    for design in DESIGNS:
        ex_rng = random.Random(SEED + 1)  # the example sentences have the same content in every design
        parse_items = [{"id": f"p{i}", "text": render(s, design, root_of, affix_of)}
                       for i, s in enumerate(sentences[:N_PARSE])]
        gen_items = [{"id": f"g{i}", "gloss": gloss(s)} for i, s in enumerate(sentences[N_PARSE:])]
        materials[design] = {"spec": spec_text(design, root_of, affix_of, ex_rng),
                             "parse": parse_items, "generate": gen_items}
        gold["designs"][design] = {
            "parse": {f"p{i}": {"gloss": gloss(s),
                                "morphemes": [root_of.get(m) or affix_of[m] for w in s for m in w]}
                      for i, s in enumerate(sentences[:N_PARSE])},
            "generate": {f"g{i}": render(s, design, root_of, affix_of)
                         for i, s in enumerate(sentences[N_PARSE:])},
        }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "materials.json").write_text(json.dumps(materials, ensure_ascii=False, indent=1))
    (out_dir / "gold.json").write_text(json.dumps(gold, ensure_ascii=False, indent=1))
    lengths = [sum(len(w) for w in s) for s in sentences]
    print(f"saved to {out_dir}; morphemes per sentence min={min(lengths)} max={max(lengths)} "
          f"mean={sum(lengths) / len(lengths):.1f}")


def _norm_gloss(g: str) -> str:
    return " ".join(g.replace(" - ", "-").split()).lower()


def score(out_dir: Path, answers_path: Path) -> None:
    """answers.json: {"<condition>": {"design": ..., "parse": [{id, morphemes, gloss}], "generate": [{id, text}]}}"""
    gold = json.loads((out_dir / "gold.json").read_text())["designs"]
    answers = json.loads(answers_path.read_text())
    report = {}
    for cond, ans in answers.items():
        g = gold[ans["design"]]
        parse = {a["id"]: a for a in ans.get("parse", [])}
        gen = {a["id"]: a for a in ans.get("generate", [])}
        seg_ok = sum(1 for k, v in g["parse"].items()
                     if [m.lower() for m in parse.get(k, {}).get("morphemes", [])] == v["morphemes"])
        gloss_ok = sum(1 for k, v in g["parse"].items()
                       if _norm_gloss(parse.get(k, {}).get("gloss", "")) == _norm_gloss(v["gloss"]))
        gen_ok = sum(1 for k, v in g["generate"].items() if gen.get(k, {}).get("text", "").strip() == v)
        errors = [{"id": k, "want": v, "got": gen.get(k, {}).get("text")}
                  for k, v in g["generate"].items() if gen.get(k, {}).get("text", "").strip() != v]
        errors += [{"id": k, "want": v["gloss"], "got": parse.get(k, {}).get("gloss")}
                   for k, v in g["parse"].items()
                   if _norm_gloss(parse.get(k, {}).get("gloss", "")) != _norm_gloss(v["gloss"])]
        report[cond] = {"design": ans["design"], "segmentation": f"{seg_ok}/{len(g['parse'])}",
                        "gloss": f"{gloss_ok}/{len(g['parse'])}", "generate": f"{gen_ok}/{len(g['generate'])}",
                        "errors": errors}
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "materials":
        make(Path(sys.argv[2]))
    elif sys.argv[1] == "score":
        score(Path(sys.argv[2]), Path(sys.argv[3]))
