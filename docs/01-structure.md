# 01. Language structure

> **What changed after the stage-2 experiment** (see [02. Spelling and morphemes](02-tokens-and-forms.md))
> - L0: use spaces. Put one space between words.
> - L1: the "CVC root + VC affix, glued (no spaces)" sketch below is withdrawn. Almost no VC affix candidates pass the word filter, and glued spelling misaligns token boundaries.
> - L2: propose an analytic language instead of an agglutinative one. Attaching affixes adds tokens.
> - L4: mark roles with word order instead of case affixes.
> - L5: omit default values instead of marking them obligatorily.
> - L6: not built (D-004).
>
> The text below is kept as the review record from stage 1.

We split the language into the layers below and settle them one at a time, starting from the bottom, because decisions in a lower layer limit the options in the layers above.

```
L6  Obfuscation layer (optional)   key-based vocabulary substitution, etc.
L5  Discourse and pragmatics       referents, confidence, source, speech act
L4  Syntax                         words → sentences
L3  Lexicon and semantics          how concepts are assigned to roots
L2  Morphology                     morphemes → words
L1  Morpheme shape                 letters → morphemes, finding boundaries
L0  Character set                  which letters to use
```

Each section follows the order options → assessment → recommendation → open questions.
All recommendations are **proposals**. Once settled, they are recorded in the progress table in the [README](../README.md).
The meanings of the roots and affixes in the examples below are arbitrary and serve only to illustrate the structure.

---

## L0. Character set

**Options**

- (a) 26 lowercase letters
- (b) 52 letters, upper and lower case
- (c) lowercase letters + space and punctuation

**Assessment**

- Distinguishing case raises the information per character, but mixed-case strings split badly into tokens (a G4 loss). The token cost is large compared with the confusion it causes humans.
- Spaces make token boundaries clean, which helps the AI (G1, G4), but they show humans the word boundaries directly (a G2 loss).
- With no digits or symbols, we need a way to write numbers and foreign strings (proper nouns, code, URLs) in letters only (covered in L3).

**Recommendation**: use only the 26 lowercase letters a–z. Leave the use of spaces as an **experimental variable**, to be settled in the stage-2 tokenization experiment.

Letter classes used in L1:

- Vowels V = {a, e, i, o, u} (5 letters)
- Consonants C = the other 21 letters (including y)

**Open questions**: should y count as a vowel? Should letters that tokenize badly (q, x, etc.) be dropped?

---

## L1. Morpheme shape and finding boundaries

Without spaces, the letters themselves must show where to split (self-segmenting).

**Options**

| Approach | Description | Problem |
|---|---|---|
| (a) Fixed length | Every morpheme is 3 letters | Finding boundaries requires counting letters (an LLM weakness) |
| (b) Shape-based | The consonant/vowel pattern shows the morpheme type and its boundaries (as Lojban uses word shapes such as CVCCV to tell word types apart) | Shape rules limit how many forms are available |
| (c) Prefix code | Assign morphemes so that no morpheme is the start of another | Cannot be split without the dictionary |
| (d) Length-marking letter | The first letter signals the morpheme's length | Requires counting letters (an LLM weakness) |

**Recommendation (sketch)**: shape-based, with two morpheme types

| Type | Shape | Maximum count | Role |
|---|---|---|---|
| Root | CVC | 21 × 5 × 21 = 2,205 | Meaning (things, actions, qualities) |
| Affix | VC | 5 × 21 = 105 | Grammar (case, tense, confidence, etc.) |

There is one segmentation rule: **if the next letter is a consonant, read a root (3 letters); if it is a vowel, read an affix (2 letters).**
It needs only one letter of lookahead, so it is deterministic and requires no letter counting.

```
katenmirob  →  kat | en | mir | ob
               root affix root affix
```

- Pros: it is built mostly from pronounceable syllables, so it is likely to be tokenizer-friendly, and it parses without spaces.
- Risk: the tokenizer may cut `katenmirob` out of line with the morpheme boundaries, for example `k|aten|mir|ob`. This is **the key question for the stage-2 experiment**.
- We do not need all 2,205. Drop the ones that overlap with English words or romanized Korean words (cat, dog, man, bap, etc.) (G2).
  Dropping consonants that tokenize badly reduces the count (e.g. 16 consonants → 16 × 5 × 16 = 1,280).

**Open questions**: are 5 vowels enough? What is the upper limit on the number of roots?

---

## L2. Morphology (how words are built)

| Type | Example languages | Features | AI decoding (G1) | Human resistance (G2) |
|---|---|---|---|---|
| Isolating | Chinese, Vietnamese | One word = one morpheme; grammar shown by word order | Good | Low |
| Agglutinative | Korean, Turkish, Finnish | Root + chain of affixes; one affix = one meaning | **Very good** | Medium |
| Fusional | Latin, Russian | Several meanings fused into one affix; many irregular forms | Poor | High |
| Polysynthetic | Inuit, Ithkuil | A whole sentence is one word | Medium | Very high |
| Root-and-pattern | Arabic (k-t-b → kataba "he wrote", kitāb "book") | Consonants = meaning, vowels between them = grammar | **Poor** (the meaning is spread over separated letters, out of line with tokens) | High |

**Recommendation**: **agglutinative**. One meaning per affix, no exceptions.
The rules are compositional, which suits in-context learning best (G1) and makes a parser easy to build (G3).
Human resistance comes from the vocabulary (L3) and information density, not from complex morphology.

**Word boundaries**: a root starts a new word. Compounds (root + root) are marked explicitly with a linking affix.

```
kat | ol | mir | ob   →   [kat-ol-mir]-ob     (assume ol = compound linking affix)
```

**Open questions**: affix order rules (e.g. derivation → number → case → confidence)

---

## L3. Lexicon and semantics

| Approach | Description | G1 | G2 | Notes |
|---|---|---|---|---|
| Arbitrary assignment (a priori) | A random root for each concept | Needs the whole dictionary | **Very high** | Dictionary size = spec size |
| Taxonomic (Wilkins 1668, Ro) | Each letter narrows the category (first letter = top-level class …) | Even unseen words can be guessed | Low (once the system is learned, everything is readable) | Hard to fix if the classification is wrong |
| Semantic primitives (NSM, Toki Pona) | Combine a few dozen to about a hundred basic concepts | Very small dictionary | Medium | Expressions become long and ambiguous (a G4 loss) |
| Embedding coordinates | Concept = quantized coordinates in an AI's embedding space | **Not possible** | - | Each model has a different space, and an LLM cannot see its own embeddings through text |
| Hybrid | Core roots (randomly assigned) + composition rules + domain-specific roots | Good | High | |

Embedding coordinates look like the best fit for "a language only AI understands", but in practice they do not work.

**Recommendation**: **hybrid**

- Randomly assign 500–1,000 core roots to high-frequency concepts (drawing on lists of semantic primitives and high-frequency vocabulary).
- Extend systematically with derivational affixes (e.g. action → agent, quality → opposite quality).
- Estimated dictionary size: 1,000 roots × about 8 tokens per entry ≈ 8,000 tokens. That fits easily in a context, but for a human it is months of memorization.
  **This gap is the core asymmetry of this language.**

**Required escape hatches**

- Numbers: a fixed syllable for each digit 0–9 (base 10). LLMs are weak at character-level arithmetic, so a simple mapping is better than a clever scheme such as base conversion.
- Foreign strings (proper nouns, code, URLs): put the original spelling unchanged between start-quote and end-quote markers. How to write characters outside a–z is undecided.

**Open questions**: where should the list of core concepts come from? Should concepts with close meanings get similar roots (easier to learn, but lower resistance)?

---

## L4. Syntax (sentence structure)

| Approach | Description | Pros | Cons |
|---|---|---|---|
| Fixed word order | Position decides the role (SOV, SVO) | Simple | Omission and inversion are hard |
| Case marking + free word order | Roles marked with affixes, like Korean particles | Meaning survives reordering, which confuses humans | Several sentences for the same meaning (no canonical form) |
| Prefix notation (the predicate fixes the number of arguments) | As in `f x y`, the predicate fixes the argument count, so no brackets are needed | Fully unambiguous; resembles code | The structure cannot be seen without the dictionary, and one wrong word breaks the whole sentence |
| Predicate first + case marking + clause boundary markers | Predicate → arguments with role marks; embedded clauses get opening and closing affixes | Unambiguous; each argument states its own role | More affixes |

**Recommendation**: **predicate first + case marking + clause boundary markers**

- Why predicate first: it has the same shape as the function call `give(giver, gift, recipient)`, which LLMs have seen in huge volumes in training, and when generating, the model fixes the relation first and then fills in the arguments.
- Attach a role (agent, theme, beneficiary, instrument, location …) to each argument as an affix, so the structure can be parsed without the dictionary.
- Fix a canonical order so that the same meaning always becomes the same string (G3; helps automatic evaluation). Keep free word order as an L6 obfuscation option.

```
Meaning:   The user sent the file to me (certain, directly observed)
Structure: [send-past-certain-observed] [user-agent] [file-theme] [me-beneficiary]
```

**Open questions**: the size of the semantic role list, the position of modifiers (adjectives and adverbs), how to mark relative clauses

---

## L5. Discourse and pragmatics: AI-specific grammatical categories

Some information that natural languages lack or leave optional is useful when AIs talk to each other. We can make it a **mandatory grammatical category**.
This is where this language differs from a simple cipher.

| Category | Example values | Natural-language counterpart |
|---|---|---|
| Confidence | certain / high / low / unknown | English "probably" (optional) |
| Evidentiality (source) | direct observation / inference / user statement / tool result / prior knowledge | Korean "-deora", "-dae"; evidentiality in Turkish and Quechua |
| Speech act | assertion / question / request / command / proposal | Korean sentence endings (-da, -ni, -ja, -ra) |
| Referents | numbered variables (①, ②) instead of pronouns | None (natural-language pronouns are ambiguous) |
| Quantifier scope | all / some / none + explicit scope | ∀, ∃ in logic |

**Recommendation**: mark confidence, evidentiality and speech act in every sentence. Write referents as numbered variables.

**Open questions**: the more mandatory categories, the longer short sentences become (a G4 loss). Should there be a rule that omits default values?

---

## L6. Obfuscation layer (optional)

If the goal is to hide content from humans, the communicating parties can share a key (seed) and use it to shuffle the root assignment table.
People without the key (and other AIs) cannot read it.
But this is a morpheme-level substitution cipher, so once enough sentences pile up, frequency analysis can break it. If you need security, use standard encryption.

**Recommendation**: on hold. Decide once the project's purpose is settled.

---

## Roadmap

| Stage | Content | Deliverables |
|---|---|---|
| 1 | Settle the purpose, design principles and layer structure (this document) | `docs/00`, `docs/01` |
| 2 | Settle L0–L1 + tokenization experiment (with or without spaces, consonant set, match rate between morpheme and token boundaries) | Experiment scripts, results |
| 3 | L2 grammatical affix list and ordering rules | Affix table |
| 4 | L3 assignment of 300–500 core roots | Dictionary |
| 5 | L4 syntax + reference parser | Grammar spec, parser code |
| 6 | L5 AI-specific categories | Spec additions |
| 7 | Iterative improvement with an LLM evaluation harness | Evaluation scripts, score tables |
