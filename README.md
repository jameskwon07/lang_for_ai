# lang_for_ai

**Can we build an alphabetic language that humans cannot read and that only AIs read and write among themselves?** Can that language save tokens in AI-to-AI communication?

This is a stage-by-stage record of experiments on these questions. The experiment is finished.

## Conclusion

> **It can be built. But for AI-to-AI use it was not better than English.**
>
> - Claude read this language with 95–100% accuracy after reading only the spec (about 10,000 tokens).
> - But **when it wrote the language itself**, 7.5–40% of the information leaked, and the token count was about the same as plain English (0.92–1.11x).
> - **Terse English**, which drops articles and similar words, is readable without a spec, and no design beat it on held-out messages.

## What it looks like

| | Message | Tokens (o200k / Claude proxy) |
|---|---|---|
| English | Find recent peer-reviewed studies on how sleep deprivation affects working memory. Return the five most relevant, each with a one-sentence summary. | 27 / 28 |
| Terse English | Find recent peer-reviewed studies: sleep deprivation -> working memory. Return top 5, 1-sentence summary each. | 24 / 23 |
| **This language (LEAN)** | `aqu antib persec despe adap tob obliv sovere consec afges agreg fle oll fres swo flav avut anunc conv` | 20 / 24 |
| What Claude read back from the spec alone | Find recent peer-reviewed studies about how sleep loss affects working memory, and return the 5 most relevant ones, with a one-sentence summary for each. | |

This example is a design-set message, so it favors this language. On messages not used in the design, this language was 7–34% longer than terse English.

## Experiments and results

| Stage | Question | What we did | Result | Details |
|---|---|---|---|---|
| 1. Design principles | What structure should it have? | Listed the differences between humans and LLMs, split the language into 7 layers (characters → morphemes → … → pragmatics) and reviewed the options | The key risk is tokenization. LLMs see tokens, not characters | [00](docs/00-foundations.md), [01](docs/01-structure.md) |
| 2. Spelling | How should the letters be written so that AI reads them cheaply? | Measured 100,000 form candidates and 5 spelling schemes on 7 tokenizers; Claude read/write pilot | **Lowercase + one space between morphemes** is best. On 5 of 7 tokenizers, one morpheme costs 1.01 tokens | [02 §2](docs/02-tokens-and-forms.md#2-spelling-l0-l1) |
| 3. Token savings | Can it be shorter than English? | A corpus of 40 AI agent messages, projection of the draft grammar, rebuttal attempts by 2 agents arguing for this language, a generalization test on held-out messages | The draft grammar costs 1.26–2.20x terse English. Even the best design (LEAN) costs **1.07–1.34x terse English** on held-out messages, and 0.81–0.99x plain English | [02 §3](docs/02-tokens-and-forms.md#3-token-savings) |
| 4. Reading | Does Claude read it from the spec alone? | Gave a fresh Claude only the spec and the messages, had it translate them back into English, and graded the results blind | Default model **98%**, Haiku 86%. On a design with many devices (KODEX), Haiku **5%** | [02 §3.4](docs/02-tokens-and-forms.md#34-does-claude-actually-read-it) |
| 5. Writing and trade-offs | What if it writes the language itself? Is there a reason to use it instead of English? | Write-then-read round trip in which one Claude writes and another Claude reads; analysis from 5 perspectives + critique | When the default model writes, **88–93%** is preserved and tokens are 0.92–1.11x plain English. When Haiku writes, 60–63% is preserved | [03](docs/03-tradeoffs.md) |

## What a separate language changes (vs plain English, terse English, JSON)

| What gets better | What gets worse | What stays the same |
|---|---|---|
| With careful encoding, messages are 1–19% shorter than plain English (gone when the model writes them itself) | A fixed spec cost of about 10,000 tokens in every conversation | Accuracy when a strong model reads |
| Content is hidden from people without the spec (this is not security) | 7.5–40% information loss when the model writes directly | Expressing confidence and evidence |
| Value as an experiment | Reading and writing drop sharply on weaker models | Passing paths, URLs and numbers |
| | Oversight by humans and keyword filters gets harder | Security (neither has any) |
| | Costs of spec versioning, dictionary maintenance, debugging and integration with JSON tools | |

The full comparison tables and evidence are in [03. What a separate language changes](docs/03-tradeoffs.md).

## Lessons

1. **It is hard to beat English inside an English tokenizer.** English words are already single tokens. The only cheap forms left for a new language are the leftover pieces, and 68% of the LEAN dictionary entries are prefixes of common English words.
2. **The advantage on the design examples was overfitting.** On design-set messages, both designs beat terse English on most tokenizers. On held-out messages, they lost on every tokenizer.
3. **Reading is easy; writing is hard.** Claude read the same language almost perfectly, but leaked information when it wrote it. Weaker models mixed in English words.
4. **The design must be simple for weaker models to use it.** The same Haiku read 86% of a simple design and 5% of a design with many devices.
5. **The spec cost outweighs the per-message savings.** Even if each message saves a few tokens, paying back a 10,000-token spec in every conversation takes tens to hundreds of messages per API call. On the Claude proxy tokenizer, the cost was effectively unrecoverable.

## Limitations

- The subjects (reading and writing) and the judges are all Claude. We did not measure models from other companies.
- The current Claude tokenizer is not public, so we used the Claude 2-era tokenizer (`claude_legacy`) as a proxy.
- There are 20–40 messages, and each condition was run once.
- We did not run a control that writes and reads back in terse English or JSON.

## Repository layout

| Path | Contents |
|---|---|
| [docs/](docs/) | Design principles (00), language structure (01), spelling and token experiments (02), trade-off analysis (03), [decision log](docs/decisions.md) |
| [experiments/tokenization/](experiments/tokenization/) | Measurement scripts for 7 tokenizers, the AI message corpus, rebuttal checks and reading-experiment records. Its README explains how to reproduce the results |
| [experiments/tradeoffs/](experiments/tradeoffs/) | Raw data for the trade-off analysis and the write-then-read round trip |

The documents were first written in Korean; those versions are in the git history. Some raw data and experiment materials stay in their original Korean, for example the `ko` field of the corpus, the pilot task files given to subjects (`experiments/tokenization/results/pilot/task_*.md`) and the code that generates them, and raw agent outputs (gloss notes, analyst and critic JSON, note fields in result JSON, the fact-check report that quotes the Korean docs, and the invalid first-run Haiku answer).

To reproduce:

```bash
cd experiments/tokenization
pip install -r requirements.txt
python3 fetch_tokenizers.py   # downloads the 7 tokenizers from PyPI packages
python3 inventory.py && python3 alignment.py && python3 baseline.py && python3 projection.py
```

## License

[MIT License](LICENSE)
