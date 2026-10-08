# Decision log

Only final decisions are recorded here. Options still at the proposal stage are in each design document.

| ID | Date | Decision | Rationale / outcome |
|---|---|---|---|
| D-001 | 2026-10-07 | The license is MIT | The simplest permissive license, easy to use for both documents and code |
| D-002 | 2026-10-07 | The purpose is **AI-to-AI communication, token savings, and a pure experiment** | Token efficiency (G4) moves up in priority. Savings only matter if they exceed the spec cost |
| D-003 | 2026-10-07 | AIs read and write the language **by receiving the spec in context** (in-context learning) | The spec size is itself a cost, so the spec must stay small. Fine-tuning remains a later option |
| D-004 | 2026-10-07 | Human read resistance is sufficient if **the meaning cannot be guessed without the spec** | We do not build the L6 obfuscation layer. Spellings that show boundaries to humans, such as spaces, are also allowed |
| D-005 | 2026-10-08 | For token savings, **being cheaper than plain English is enough**. Continue with a focus on experimentation and clarity | In stage 2, no design beat terse English on held-out messages ([02 §3.3](02-tokens-and-forms.md#33-rebuttal-attempts-can-anything-beat-terse-english)) |
| D-006 | 2026-10-08 | Do not measure separately with the current Claude tokenizer | Claude-related token figures remain claude_legacy (Claude 2-era) proxy values, and this is stated as a limitation |
| D-007 | 2026-10-08 | Adopt the stage-2 design changes | L0: lowercase a–z + one space between words. L1: one word = one morpheme; forms are chosen by a tokenizer vocabulary scan and selection rules. L2: analytic. L4: roles marked by word order. L5: defaults omitted ([02 §5](02-tokens-and-forms.md#5-proposed-design-changes)) |
| D-008 | 2026-10-08 | **End the experiment here** | The results are summarized in the [README](../README.md) and [03. What a separate language changes](03-tradeoffs.md) |

## Goal priorities adjusted after D-002 to D-004

| Rank | Before | After |
|---|---|---|
| 1 | G1 AI decodability | G1 AI decodability |
| 2 | G2 Human read resistance | **G4 Token efficiency** |
| 3 | G3 Unambiguity | G3 Unambiguity |
| 4 | G4 Token efficiency | G5 Expressiveness |
| 5 | G5 Expressiveness | G2 Human read resistance (met if the language cannot be read without the spec) |

When we evaluate token savings, we use not only natural English but also **terse English** (compressed English without articles and auxiliary verbs, which LLMs read without a spec) and **JSON** as comparison baselines.
The reason is that this language is only worth using if it beats the strongest competitor that works without a spec. (D-005 relaxed this criterion to "being cheaper than plain English is enough".)

## Token efficiency target after D-005

The pass mark for G4 (token efficiency) is **fewer tokens than plain English with the same content**. We still measure terse English as a comparison baseline, but beating it is not a goal.
