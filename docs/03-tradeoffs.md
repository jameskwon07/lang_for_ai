# 03. What a separate language changes

Question: if we build a separate language for the messages AIs exchange, what gets better, what gets worse, and what stays the same, compared with not building one?

The language under study is **LEAN**, which follows the design adopted in stage 2 (D-007). It is an analytic language of lowercase words separated by spaces. Its dictionary has 2,313 entries, and its spec is about 10,000 tokens.
We split "not building one" into three cases for comparison.

| Symbol | Compared with |
|---|---|
| **English** | Plain English |
| **Terse** | Compressed English without articles and auxiliary verbs. LLMs read it without a spec |
| **JSON** | Compressed JSON with a schema agreed between agents |

In the tables, ▲ means better, ▼ means worse, ＝ means about the same, and ～ means it depends on conditions. Evidence falls into three kinds. **Measured** means an experiment in this repository. **Inferred** means calculated from measurements or derived by reasoning. **External** means the literature.

## Summary

- **Few things get better, and those are conditional.** With careful encoding, messages are 1–19% shorter than plain English. When the model writes them itself from the spec alone, most of that advantage disappears. The rest is hiding content from people without the spec, and value as an experiment.
- **Many things get worse.** They include the fixed spec cost, a drop in writing accuracy (10–40 percentage points), misreading by weaker models, harder oversight by humans and monitoring tools, version and dictionary maintenance, and lost integration with JSON-based tools.
- **What stays the same** is accuracy when a strong model reads, expressing confidence and evidence, passing verbatim text such as paths and URLs, and security (there was none to begin with).
- **D-005 ("cheaper than plain English is enough") does not hold in real use.** Messages the model wrote from the spec alone were 0.92–1.11x plain English. On 4 of 7 tokenizers (including the Claude proxy), they cost more than English.

As a practical means of communication, a separate language is generally worse than English, and especially worse than terse English and JSON. The value of this project lies in the experiment.

---

## New measurement: write-then-read round trip

The biggest gap in this analysis was "when an AI writes in this language itself." Through stage 2, we measured only reading.
So we gave a Claude writer 20 messages that were not used in the design and had it write them in LEAN from the spec alone. A fresh Claude reader (the default model) then turned them back into English, and 2 judges graded the result blind against the original.

| Writer | Information preserved | Words not in the dictionary | Tokens (vs plain English) | Tokens (vs terse English) |
|---|---|---|---|---|
| Careful encoder (dictionary lookup with tools; for reference) | **100%** | 0% | 0.81–0.99x | 1.07–1.34x |
| Default model (spec only) | **88–93%** | 0% | **0.92–1.11x** | 1.21–1.49x |
| Haiku low effort (spec only) | **60–63%** | **26%** | 0.65–0.73x | 0.85–0.98x |

- **The advantage appears only when encoding is done with care.** Messages the default model wrote from the spec alone were 11–13% longer than the careful encoder's. On the Claude proxy tokenizer, they cost 11% more than plain English. The cost of the tool calls and thinking tokens spent on careful encoding is not included in any measurement.
- **Haiku wrote short but wrong.** 26% of its words were English words not in the dictionary (`part`, `hour`, `risk`…), and it also left out content. The messages were shorter because information was lost.
- **The weaker model also went off task.** In the first run, the Haiku writer did not write in this language. Instead, it answered, in Korean, the user question that was passed along with the task. The table above is from a rerun with the task pinned down. The prompt setup is also a factor, so the cause cannot be pinned down.

Data: `experiments/tradeoffs/roundtrip/`

---

## 1. What gets better

| Item | English | Terse | JSON | Size | Evidence |
|---|---|---|---|---|---|
| Message body tokens (with careful encoding) | ▲ | ▼ | ▲ | 1–19% shorter than English (0.2–5.9 tokens per message). 7–34% longer than terse English | Measured |
| Hiding content from people without the spec | ▲ | ▲ | ▲ | Small. Verbatim text such as paths and names stays visible, and one spec is enough to decode it | Measured |
| Experimental and research value | ▲ | ▲ | ▲ | Medium. Examples: Haiku's reading split between 86% and 5% depending on how simple the design was; the token advantage shrank at each step, from design-set messages to held-out messages to writing from the spec alone | Measured |

Things that get better only under certain conditions:

| Item | English | Terse | JSON | Condition | Evidence |
|---|---|---|---|---|---|
| Machine validation (closed vocabulary, fixed grammar) | ～ | ～ | ▼ | **A parser has to be built** (none exists yet). Once built, it makes format checks easier than in English, but it cannot catch errors where the wrong word was chosen. JSON already has mature validators | Inferred |

In real use, the token advantage is "～". When the model writes from the spec alone, messages are 0.92–1.11x plain English (round trip above).

## 2. What gets worse

### 2.1 Cost

| Item | English | Terse | JSON | Size | Evidence |
|---|---|---|---|---|---|
| Fixed spec cost | ▼ | ▼ | ▼ | 8,417–10,282 tokens per context. At Opus 5.5 pricing, about $0.002 per call for a cache read, and about $0.05 (5 minutes) to $0.08 (1 hour) for a cache write | Measured |
| Total cost including the spec | ▼ | ▼ | ▼ | For writing from the spec alone, 4 of 7 tokenizers have no break-even point. The other 3 break even only when one call writes 68–120 messages (341–601 on the reading side). A typical agent call writes one message | Measured, inferred |
| Context window usage | ▼ | ▼ | ▼ | Always takes up about 1% of a 1M window and about 5% of a 200K window | Measured |
| Tokenizer and model dependence | ▼ | ▼ | ▼ | Savings swing between 1% and 19% depending on the tokenizer. Every model change requires revalidation and rewriting the cache | Measured |
| Thinking (reasoning) tokens | ▼ | ▼ | ～ | **Not measured.** If the writer spends just 0–5.9 extra thinking tokens per message, the savings disappear | Inferred |
| Latency | ▼ | ▼ | ～ | Small. When the cache is cold, spec processing and thinking tokens add to it | Inferred |

### 2.2 Accuracy

| Item | English | Terse | JSON | Size | Evidence |
|---|---|---|---|---|---|
| Accuracy when writing directly | ▼ | ▼ | ▼ | Default model −7.5 to −12.5 percentage points, Haiku −37.5 to −40 percentage points (vs careful encoding) | Measured |
| Reading by weaker models | ▼ | ▼ | ▼ | Haiku 86% vs default model 98%. 5% on a design with many devices (KODEX) | Measured |
| Misreading sentence structure (clause boundaries, scope, speech act) | ▼ | ▼ | ▼ | Haiku misread 4 of 20 messages; the default model misread 0 | Measured |
| Vocabulary gaps and circumlocutions | ▼ | ▼ | ▼ | Each held-out message needed 2.9 circumlocutions and 0.3 new entries | Measured |
| Information omitted by design (tense, number, order) | ▼ | ▼ | ～ | Small. The Haiku reader made minor errors in 4–5 of 20 messages. Both models missed an order such as "first / then" once each | Measured |
| Loss accumulating over multi-hop relays | ▼ | ▼ | ▼ | If a message is rewritten each time it passes through an agent, losses add up. Taking 88–93% retention per hop gives 77–86% over two hops and 68–80% over three | Inferred |
| When the spec is missing | ▼ | ▼ | ▼ | Total failure. If the spec gets truncated in a long conversation or a different version gets mixed in, the meaning changes with no error signal | Inferred |

### 2.3 Operations

| Item | English | Terse | JSON | Size | Evidence |
|---|---|---|---|---|---|
| Spec versioning | ▼ | ▼ | ▼ | Adds a component that English did not have. A version mismatch silently changes the meaning | Inferred |
| Dictionary growth and maintenance | ▼ | ▼ | ▼ | Of the 2,313 dictionary entries, 2,039 (88%) do not even have a part of speech yet | Measured |
| Debugging, incident investigation, audit logs | ▼ | ▼ | ▼ | Every log investigation gets an extra decoding step. The combined loss from writing and decoding is 7.5–40% | Measured |
| Integration with tool calls, APIs and agent frameworks | ▼ | ▼ | ▼ | JSON is the default format for tool calls. This language does not turn into values that code can use directly | Inferred |
| Testing and quality assurance | ▼ | ▼ | ▼ | More axes to test (reading, writing, per model, per version) | Inferred |

### 2.4 Safety and oversight

| Item | English | Terse | JSON | Size | Evidence |
|---|---|---|---|---|---|
| Direct reading and oversight by humans | ▼ | ▼ | ▼ | Humans cannot read it without tools (as designed). Because each word is one morpheme, dictionary substitution alone gives a literal translation of 95%, so a glossing tool could reduce this | Inferred, measured |
| Cost of monitoring with an LLM | ▼ | ▼ | ▼ | Just the output of translating back into English for monitoring is about 30 tokens per message. That is more than 5 times the savings (at most 5.9 tokens) | Inferred |
| Keyword- and classifier-based monitoring | ▼ | ▼ | ▼ | Filters without the spec catch almost none of the meaning-bearing keywords. Conversely, 68% of the dictionary (1,571 entries) are the beginnings of common English words, so forms that look like risky words (e.g. `homic`) appeared in 14 of 40 messages. Both false negatives and false positives occur | Measured |
| Risk of bypassing model safety training | ▼ | ▼ | ▼ | Not measured for this language. In the literature, safeguards worked less well in low-resource languages or ciphers (Yong et al. 2023 "Low-Resource Languages Jailbreak GPT-4", Yuan et al. 2023 "GPT-4 Is Too Smart To Be Safe") | External |
| Detecting covert channels and collusion | ▼ | ▼ | ▼ | In a channel that humans find hard to read, unintended information that gets mixed in is hard to notice. Not measured | Inferred |
| Separating instructions from data (prompt injection) | ▼ | ▼ | ▼ | Verbatim spans and text in the language are mixed together, and monitoring is hard, so injections are easy to miss. Not measured | Inferred |
| Trust and social acceptance | ▼ | ▼ | ▼ | Small in a pure experiment, larger in a real deployment | External, inferred |

## 3. What stays the same

| Item | English | Terse | JSON | Details | Evidence |
|---|---|---|---|---|---|
| Accuracy when a strong model reads | ＝ | ＝ | ＝ | The default-model reader recovered 95–100% of the information in carefully encoded messages (98% on design-set messages, 95–100% on held-out messages) | Measured |
| Expressing and preserving confidence, evidence and speech act | ＝ | ＝ | ＝ | All 3 relevant messages were preserved. The current design does not require these markers, so it is the same as English. Making them mandatory erases the token advantage (02 §3.2) | Measured |
| Passing paths, URLs, identifiers and numbers | ＝ | ＝ | ＝ | Carried unchanged in verbatim spans. About 12% of message tokens. 0 errors in numbers or verbatim text | Measured |
| Actual security (confidentiality, integrity, authentication) | ＝ | ＝ | ＝ | Neither has any. Obscuring that one spec can undo is not security. It only adds an illusion of security | Inferred |
| Same meaning = same string? | ＝ | ＝ | ～ | No. When two writers wrote the same messages, the lengths differed by 11–13%. JSON guarantees it only for enum fields | Measured |

## 4. What this means for the project

1. **D-005 needs to be revisited under real-use conditions.** "Cheaper than plain English" held only with careful encoding. When the model writes from the spec alone, it breaks on 4 tokenizers, including the Claude proxy. Three paths remain:
   - Continue for experimental purposes only. Measure tokens only as a metric.
   - Help the writer. For example, a dictionary lookup tool would let it write like the careful encoder, but the cost of those tool calls must be measured too.
   - Refine the design again. Assign parts of speech, fill the gaps that produced many circumlocutions, and clean up forms that are easy to confuse.
2. **Some of what gets worse can be reduced with tools.** A single parser-glosser improves machine validation, human oversight and debugging together. Because each word in this language is one morpheme, it is also relatively easy to build.
3. **Some of it cannot be reduced.** The fixed spec cost, the accuracy of weaker models, version management and the risk of bypassing safety training remain as long as a separate language is used.

## 5. Limitations

- 20 messages, 1 valid run per condition.
- **There is no control.** We did not run a write-then-read test in terse English or JSON. So "worse than terse English and JSON" in the accuracy items is inferred, and we cannot separate the loss from compression itself from the loss specific to this language.
- The writers, readers, judges and analysts are all Claude. We did not measure models from other companies.
- We did not measure with the current Claude tokenizer (D-006). The Claude figures come from the Claude 2-era tokenizer.
- We did not measure thinking tokens, latency, prompt injection or safety-training bypass.

Data: raw output from the 5 analysts in `experiments/tradeoffs/analysts.json`, the critic's consolidated version in `experiments/tradeoffs/critique.json`, and the round trip in `experiments/tradeoffs/roundtrip/`.
