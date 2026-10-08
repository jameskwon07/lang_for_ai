# Pilot: Claude's reading and writing accuracy by spelling scheme

We wrote a toy language built with `pilot_segmentation.py` (24 CVC roots, 12 VC affixes) in four spellings.
Claude subjects received only the spec and were asked to analyze 20 sentences (morpheme segmentation + gloss) and to generate 20.
Subjects read only one task file and used no other tools (confirmed from the run logs). The task files are `pilot/task_*.md`, the answers are `pilot/answers.json`, and the gold answers are `pilot/gold.json`.

- Conditions: default = the session's default model, haiku-low = Claude Haiku + low reasoning effort
- Morphemes per sentence: 4–17 (mean 11.2); the 20 analysis sentences contain 231 morphemes in total

## Accuracy (correct sentences / 20)

| Spelling | Condition | Segmentation | Gloss | Generation |
|---|---|---|---|---|
| camel | default | 20/20 | 20/20 | 20/20 |
| camel | haiku-low | 20/20 | 18/20 | 20/20 |
| nospace | default | 20/20 | 20/20 | 20/20 |
| nospace | haiku-low | 20/20 | 20/20 | 20/20 |
| spaced | default | 20/20 | 20/20 | 20/20 |
| spaced | haiku-low | 20/20 | 15/20 | 20/20 |
| wordspaced | default | 20/20 | 20/20 | 20/20 |
| wordspaced | haiku-low | 20/20 | 20/20 | 20/20 |

## Errors

There were no segmentation errors. All 7 errors were vocabulary confusions in the haiku-low condition.

- camel/haiku-low p0: gold `fix-CERT result-PL-INS` / answer `fix-CERT result-PL-AGT`
- camel/haiku-low p4: gold `write-CERT file-PL-INS` / answer `write-CERT file-PL-AGT`
- spaced/haiku-low p2: gold `delete-INFR plan-PL-PAT agent-PL-REC user-INS result-SRC` / answer `delete-INFR plan-PL-PAT agent-PL-REC user-INS file-SRC`
- spaced/haiku-low p3: gold `check-NEG-INFR server-AGT task-PL-PAT message-new-PL-REC result-new-SRC` / answer `check-NEG-INFR server-AGT task-PL-PAT message-new-PL-REC file-new-SRC`
- spaced/haiku-low p7: gold `check-PST-CERT-Q result-PL-AGT server-PL-REC server-PL-INS tool-PL-SRC` / answer `check-PST-CERT-Q file-PL-AGT server-PL-REC server-PL-INS tool-PL-SRC`
- spaced/haiku-low p15: gold `find-FUT-INFR message-old-PL-AGT tool-PAT error-PL-REC result-large-SRC` / answer `find-FUT-INFR message-old-PL-AGT tool-PAT error-PL-REC file-large-SRC`
- spaced/haiku-low p17: gold `read-NEG-CERT result-AGT result-PAT error-small-INS message-SRC` / answer `read-NEG-CERT file-AGT file-PAT error-small-INS message-SRC`

- spaced, 5 errors: the roots `fek` (result) and `kef` (file) were confused. The two forms use the same letters in a different order.
- camel, 2 errors: the affix `Ag` (INS) was read as AGT. The form `ag` matches the first letters of `AGT`, the label of another affix.

## Token counts of the analysis sentences (tokens per morpheme)

| Spelling | o200k | cl100k | claude_legacy | llama3 | llama4 | mistral_tekken | mistral_sp |
|---|---|---|---|---|---|---|---|
| nospace | 1.25 | 1.33 | 1.25 | 1.31 | 1.19 | 1.25 | 1.38 |
| spaced | 1.14 | 1.38 | 1.44 | 1.35 | 1.22 | 1.36 | 1.48 |
| wordspaced | 1.16 | 1.33 | 1.31 | 1.31 | 1.19 | 1.26 | 1.42 |
| camel | 1.45 | 1.70 | 1.72 | 1.70 | 1.49 | 1.66 | 1.80 |

This toy vocabulary was not chosen to fit the tokenizers. So one space between morphemes (spaced) is not cheaper than glued spelling here.

## Limitations

- Each condition was run only once, and there are only 40 items. The default model scored full marks on all four spellings, so the test could not separate the spellings (ceiling effect).
- The only subject is Claude. We did not measure models from other companies.
- The toy language is much smaller and simpler than the real design.
