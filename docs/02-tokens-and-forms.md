# 02. Spelling and morphemes: tokenization results (stage 2)

After the purpose was set to "AI-to-AI communication + token savings + experiment" (D-002), we ran this experiment to settle the character set (L0) and the morpheme shape (L1).
The experiment also touched on the design of the upper layers (L2–L5), and it produced an answer on the token-savings goal itself.

## Summary

1. **Put one space between morphemes, and use lowercase only.** On 5 of 7 tokenizers, the leading space costs 0 tokens, and token boundaries match morpheme boundaries. Glued spelling misaligns the boundaries, and capital letters add tokens.
2. **Choose forms by scanning the tokenizer vocabulary, not by a shape rule (CVC/VC).** Spaces mark the boundaries, so no shape rule is needed. With fixed shapes there are 205 single-token candidates; a scan of the whole vocabulary finds 657 (counting forms that are single tokens on all 7 tokenizers).
3. **The stage-1 draft grammar (agglutinative, role affixes, markers mandatory in every clause) does not save tokens.** It takes 1.26–2.20x as many tokens as terse English.
4. **Switching to a lean analytic grammar makes it cheaper than plain English, but it does not beat terse English.** On held-out messages not used in the design, it cost 1.07–1.34x terse English and 0.81–0.99x plain English. On the design-set messages it was cheaper than terse English on 5 of 7 tokenizers (0.84–0.97x), but that was overfitting.
5. **Claude reads this language with only the spec in its context (8,400–10,300 tokens, or 9,747 tokens on the Claude proxy tokenizer, claude_legacy).** The simple design (LEAN) preserved 98% of the information with the default model and 86% with Haiku at low effort. On the design with many devices (KODEX), Haiku guessed from what the words look like in English instead of using the dictionary, and scored only 5%.
6. **Almost all forms that save tokens are fragments of English words (84%).** The risk of semantic interference was actually observed (item 5).

The savings are small and the spec has a cost, so the goal needs to be reset. [Section 6](#6-decisions-needed-from-the-owner) lists the questions.

---

## 1. Method

| Item | Details |
|---|---|
| 7 tokenizers | o200k (GPT-4o and GPT-5 family), cl100k (GPT-4), claude_legacy (Claude 2 era; **a proxy, because the current Claude tokenizer is not public**), llama3, llama4, mistral_tekken, mistral_sp (32K) |
| Word filter | max zipf < 3.0 across 11 languages in wordfreq (en es de fr it pt nl tr id pl sv) |
| Corpus | 40 messages exchanged between AI agents. The same content is written in plain English (en), terse English (en_terse), Korean (ko) and JSON |
| Subjects | Claude subagents. They read only the spec file and the task file and used no other tools (confirmed from the run logs) |
| Reproduction | In `experiments/tokenization/`, run `python3 fetch_tokenizers.py`, then each script. Apart from the run-time field, the output is the same on every run. Exception: in `verify/a2_build.py`, the order of words with equal frequency changes with the hash seed, so to reproduce LEAN, use the frozen lexicon `verify/a2_lexicon_A_conservative.json` |

Details for each experiment are in `experiments/tokenization/results/*.md`. Verification records are in `experiments/tokenization/verify/`.

## 2. Spelling (L0, L1)

### 2.1 Single-token form candidates

Scripts: `inventory.py`, `verify/v_inventory.py`.

| Condition (leading space included, zipf < 3) | Single token on all 7 | On the 6 other than mistral_sp |
|---|---|---|
| CVC shape only | 32 | 50 |
| 8 shapes that start with a consonant | 205 | 319 |
| No shape limit (full vocabulary scan) | **657** | **1,344** |

- Strings that are single tokens tend to be real words. Of the CVC forms that are single tokens on all 7 tokenizers, 95% were words with zipf ≥ 3.
- 84% of the single-token forms that pass the filter are the beginnings of common English words (`calc`, `gover`). For random strings of the same length, the figure is 0%.
- Of the 105 VC (vowel + consonant) candidates for grammatical forms, only 1 passes the word filter. The stage-1 sketch (CVC root + VC affix) does not work.

### 2.2 Boundary alignment

Script: `alignment.py`.

| Spelling | Tokens per morpheme | Boundary recall / precision |
|---|---|---|
| W1 glued (no spaces) `katenmirob` | 1.10–1.26 | 0.79–0.85 / 0.67–0.75 |
| **W2 one space between morphemes** `kat en mir ob` | **1.01** (5 tokenizers), claude_legacy 1.13, mistral_sp 1.33 | 1.00 / 0.99 (5 tokenizers), claude_legacy 0.89, mistral_sp 0.75 |
| W3 one space between words | 1.02–1.19 | recall inside words 0.74–0.85 |
| W4, W5 spellings with capital letters | 1.18–1.87 | recall 0.97–1.00 |

- If the forms are chosen to fit the tokenizer, the space in W2 is free on o200k, cl100k, llama3, llama4 and mistral_tekken (`" kat"` is 1 token). Each message also takes 3.0–5.3 fewer tokens than in W1. On claude_legacy (only 88% of leading-space forms are 1 token) and mistral_sp (67%), the space is not free.
- With a vocabulary of realistic size (1,150 entries), tokens per morpheme rise to 1.04–1.08 on o200k and 1.24–1.37 on claude_legacy.

### 2.3 Claude read/write pilot

Results: `results/pilot.md`.

We wrote a toy language (24 roots, 12 affixes) in four spellings and asked Claude to analyze 20 sentences and generate 20.

| Spelling | Default model | Haiku, low effort |
|---|---|---|
| Glued (no spaces) | 60/60 | 60/60 |
| One space between morphemes | 60/60 | 55/60 |
| One space between words | 60/60 | 60/60 |
| Capital letters | 60/60 | 58/60 |

- **There were 0 segmentation errors.** The spelling does not change how well Claude understands, so choose it by token cost.
- All 7 of Haiku's errors were vocabulary confusions. They came from roots that differ only in letter order (`fek` result / `kef` file) and from forms that resemble a gloss label (`ag` INS ↔ AGT).

## 3. Token savings

This section also covers layers L2–L5.

### 3.1 Baselines

Script: `baseline.py`.

| Representation | Tokens relative to plain English (mean of 7 tokenizers) |
|---|---|
| Terse English | **0.74** |
| JSON | 1.00 |
| Korean | 1.65 (o200k 1.30, claude_legacy 2.21) |

The strongest competitor that needs no spec is terse English. Across the 40 messages, it was the cheapest in 271/280 cells (message × tokenizer).

### 3.2 Cost of the stage-1 draft grammar

Script: `projection.py`.

Two estimators independently produced morpheme analyses (36–37 morphemes per message). We turned these into actual strings and measured them.

| Scenario (cumulative) | Morphemes/message | o200k (vs terse) | claude_legacy (vs terse) |
|---|---|---|---|
| S0 draft as is | 36–37 | 1.85–1.90 | 2.17–2.20 |
| S1 omit markers for default values | 29–31 | 1.52–1.60 | 1.85–1.91 |
| S3 replace role affixes with word order | 25–27 | 1.35–1.42 | 1.67–1.72 |
| S4 remove linking and modifier markers | 24–25 | 1.29–1.33 | 1.60–1.65 |
| S5 write numbers as Arabic numerals | 22–23 | 1.27–1.30 | 1.53–1.59 |

- An independent reimplementation reproduced every figure exactly (`verify/report_audit.json`).
- Merging speech act, confidence and evidentiality into one affix gave no gain beyond omitting defaults. In this corpus, a clause almost never has more than one non-default value.
- The audit found biases against this language (shape limits on forms, a strict word filter, and others). Even with them fixed, it costs at least 1.2x as much as terse English.

### 3.3 Rebuttal attempts: can anything beat terse English?

Two agents took this language's side and each built a design. Both designed while looking at the 20 even-numbered messages.

| Design | Strategy | Spec size | Design-set messages (vs terse) | **Held-out messages (vs terse)** | Held-out messages (vs plain English) |
|---|---|---|---|---|---|
| KODEX-1 | A 2,399-entry dictionary that includes 78 stock phrases + terse grammar | 7.1K–9.1K tokens | 0.82–0.96, claude_legacy 1.03 | **1.04–1.31** | 0.78–0.97 |
| LEAN | Minimal grammar (analytic, word order, defaults unmarked) + a 2,313-word vocabulary | 8.4K–10.3K tokens | 0.84–1.01, claude_legacy 1.04 | **1.07–1.34** | 0.81–0.99 |

A different agent encoded the held-out messages (the 20 odd-numbered ones) with the spec frozen. We first checked that it reproduced the original encodings exactly, then went ahead.

- **The advantage on the design-set messages was overfitting.** KODEX's stock phrases cut tokens by 10% on the design set, but by only 2% on held-out messages.
- LEAN needed more words on held-out messages (morphemes 313 → 418). Because each word had one fixed part of speech, expressions such as "unit test" and "the fix" had to be worked around.
- Per-token efficiency did not change. Tokens per morpheme stayed at 1.04 on o200k. **It lost not because its forms were expensive, but because it used more words.**
- English tokenizers already hold most English words as single tokens. The only single-token forms a new language can use are the fragments left in the gaps. So there is almost no room to compress beyond what English has already compressed.

### 3.4 Does Claude actually read it?

Materials: `verify/readability/`.

We gave fresh Claude subjects only the spec and 20 encoded messages, and asked them to turn the messages back into English. Two judges compared the output with the originals and graded it blind (maximum 2 points per message).

| Design | Default model | Haiku, low effort |
|---|---|---|
| LEAN | **98%** (19 of 20 fully preserved) | **86%** |
| KODEX-1 | No result (timed out) | **5%** |

- When Haiku read KODEX, it did not look words up in the dictionary. It guessed from what they look like in English: it read `persu` (study) as "persuade" and `refriger` as "refrigerated". Devices such as case distinctions, stock phrases and quotes whose span is set by a count appear to have added to the load.
- LEAN's errors were on the grammar side, such as dropped sequence expressions ("first / then") and changed question forms.
- Each condition was run only once, so the causes are hypotheses.

## 4. Spec cost and break-even

Putting the spec in context costs tokens in every conversation. Caching makes it cheap, but not free.

> Sender-side break-even: number of messages sent in one API call n ≥ (spec tokens S × cache-read multiplier c) ÷ (tokens saved per message s × output price multiplier p)

Plugging in Claude's pricing structure (cache read c = 0.1, or 0.05 for Opus 5.5; output p = 5x) gives the following.

| Compared with | Savings per message s | Break-even n |
|---|---|---|
| Plain English, o200k (LEAN, held-out messages) | 4.7 tokens | about 36 per call (about 180 on the reading side) |
| Plain English, claude_legacy (LEAN, held-out messages) | 0.2 tokens | about 975 per call, about 490 for Opus 5.5 (practically impossible) |
| Terse English | negative | none |

The o200k row is an example that borrows Claude's pricing structure. We did not check other companies' actual cache discount rates.
Also, if the model thinks in English before it writes in this language, those thinking tokens (output) can exceed the savings. This cost has not been measured yet.

## 5. Proposed design changes

| Layer | Stage-1 proposal | Stage-2 proposal (rationale) |
|---|---|---|
| L0 | Lowercase a–z; spaces are an experimental variable | **Lowercase a–z + one space between words.** No capitals, digits or punctuation (2.2, cost of capitals; in KODEX, numbers were also cheaper in letter form on 6 of 7 tokenizers, with the Claude proxy as the exception) |
| L1 | CVC root + VC affix, glued (no spaces) | **One word = one morpheme.** Forms are chosen by a vocabulary scan, with no shape rule (2.1, 2.2) |
| L1 form selection rules | — | ① single token, leading space included, on the target tokenizer ② zipf < 3 in 11 languages ③ no fragments of words with similar meanings ④ avoid pairs that differ only in letter order, pairs that differ by one letter, and forms that look like the beginning of another word (2.3) ⑤ cheap forms for frequent morphemes |
| L2 | Agglutinative | **Analytic (isolating).** No inflection (3.2, 3.3) |
| L4 | Predicate first + case affixes | **Roles marked by word order** (subject-verb-object, similar to English). Case affixes cost tokens (3.2) |
| L5 | Confidence, evidentiality and speech act mandatory | **Defaults are not marked**; only non-default values are marked (3.2) |
| Spec format | — | A single all-lowercase rule, a dictionary grouped by part of speech, and as few stock phrases and special quoting devices as possible (3.4, hypothesis) |

However, even in an analytic language, fixing parts of speech too strictly increases the number of words (3.3). Whether one word may serve as both noun and verb is a question for the next stage.

## 6. Decisions needed from the owner

1. **How should the token-savings goal be set?** In this experiment, no design beat terse English on held-out messages. Savings over plain English, measured on LEAN (the design Claude could read), were 8–19% on o200k, cl100k, llama3, llama4 and mistral_tekken, 2% on mistral_sp and 1% on the Claude proxy tokenizer. Because of the spec cost, they pay off only in high-volume communication.
   - (a) Lower the token-savings goal to "being cheaper than plain English is enough", and continue with a focus on experimentation and clarity
   - (b) Keep token savings as a core goal and look for a different approach (for example, fine-tuning a model on the new vocabulary; this conflicts with D-003)
2. **Should we measure with the current Claude tokenizer?** The worst results came from the Claude proxy (Claude 2-era) tokenizer. With an Anthropic API key, we can measure on the current Claude directly through the token counting API.
3. **Should the design changes proposed in section 5 be accepted?** If they are, L0 and L1 are settled, and the next stage designs L2 and L4 (the analytic grammar and the part-of-speech system).

## 7. Limitations

- The corpus is small (40 messages), and one model wrote it in one pass. Terse English was refined while being measured on the same tokenizers, which favors the competitor.
- The morpheme counts and encodings were made by hand by agents. Someone else might produce different ones.
- The reading experiment used only Claude, once per condition. We did not measure whether models from other companies can read the language.
- We did not measure how accurately a model writes directly in this language, or how many thinking tokens it spends doing so.
