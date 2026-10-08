# 00. Foundations

## 1. Checking the premise: is "humans cannot read it, only AI can" possible?

Strictly speaking, no. For an AI to read it, the rules (the spec) must exist somewhere, and if a spec exists, a human can also decode it given time.
So in this project, "humans cannot read it" does not mean **secrecy**. It means an **asymmetry in cognitive load**.

> **Working definition**: a language whose meaning a human cannot guess without the spec, and that a human finds very hard to read and write in real time even with the spec,
> but that an LLM can read and write accurately right away once it has the spec in its context.

If you need real confidentiality, the answer is encryption. This language is a form of obfuscation, so do not use it as a security measure.

## 2. The basic fork: path A and path B

| | Path A: encoding an existing language | Path B: a new language |
|---|---|---|
| Examples | Base64, ROT13, abbreviated English | Its own vocabulary and grammar |
| How the AI understands it | Already knows it from pretraining data | Spec given in context (in-context learning); fine-tuning in the long run |
| Spec needed | No | Yes |
| What to design | Almost nothing | Everything |

Thanks to their training data, current LLMs can decode encodings such as Base64 or ROT13 directly, up to a point (errors increase with length).
So the cheapest solution to "a string that AI can read but humans cannot" already exists.
This project aims to **build a new language**, so it takes path B. Path A serves as a baseline for comparison during evaluation.

## 3. The asymmetry to exploit: how humans and LLMs differ

| Dimension | Human | LLM | Design implication |
|---|---|---|---|
| Working memory | About 4 chunks at a time | A context of hundreds of thousands of tokens | A large dictionary and long rule tables are no burden |
| Learning new vocabulary | Months for thousands of roots | Immediately, once the spec is in context | Vocabulary can be assigned at random (a priori) |
| Strings without spaces | Very hard | Relatively easy (needs verification) | Mark boundaries with grammar instead of spaces |
| Deep nesting | Hard beyond 3 levels | Handles it like code | Allow nested structures freely |
| Character-level operations (counting letters, computing positions, reversing) | Easy | **Weak** (because of tokenization) | Forbid rules that rely on character-level computation |
| Visual cues (letter case, letter shapes) | Relies on them heavily | Nearly irrelevant | Removing visual cues costs the AI nothing |

The most important trap: an LLM sees **tokens** (chunks of several characters), not characters.
Rules such as "the meaning changes every third letter" or "shift each letter by n places" can be harder for an LLM than for a human.
Avoid designs that try to make the language hard for humans and end up making it hard for the AI too.

## 4. Design goals (in priority order)

1. **G1 AI decodability**: an LLM given the spec (target: 20,000 tokens or fewer) in its context translates in both directions with high accuracy.
2. **G2 Human read resistance**: an English or Korean speaker cannot guess the meaning without the spec. Do not use roots that resemble English words, and reduce visible structure.
3. **G3 Unambiguity**: each string has exactly one parse, and a machine (a parser) can verify it.
4. **G4 Token efficiency**: express the same meaning in about as many tokens as English, or fewer.
5. **G5 Expressiveness**: it can express everyday and technical content, and its vocabulary can be extended.

### Conflicts between goals

- **G2 ↔ G4**: letter strings that are unfamiliar to humans (qzxv…) are also unfamiliar to the tokenizer, so they split into many small tokens.
  → Create unfamiliarity in "meaning assignment", not in "letter shapes".
- **G1 ↔ G2**: the more regular the language, the easier it is for the AI to learn, but also the easier it is for humans to learn.
  → Get human resistance from vocabulary size, information density and the absence of boundary marks, not from complex rules.

## 5. Evaluation method (set before the design)

| Metric | How to measure |
|---|---|
| AI comprehension | Have an LLM given the spec translate between this language and Korean, compare the output with reference translations, and measure the meaning-preservation rate of a round-trip translation (Korean → this language → Korean) |
| Model generality | Run the same tests on several models (Claude, GPT, open models) |
| Human resistance | Accuracy of guessing the meaning without the spec; time to decode one sentence after receiving the spec |
| Token efficiency | Compare the token counts of the same sentence in English, Korean and this language |
| Grammaticality | Use a reference parser to check automatically whether sentences the AI produces are grammatical |

Build the reference parser (code) early. It guarantees G3 and makes it possible to grade AI output automatically.
