# Trade-off analysis of a separate language

The conclusions are in [docs/03-tradeoffs.md](../../docs/03-tradeoffs.md).

| File | Contents |
|---|---|
| `analysts.json` | Raw classifications by 5 analysts, one per perspective (cost, accuracy, operations, safety and oversight, expressiveness) |
| `critique.json` | The critic's consolidated version, which merges duplicates and corrects overstatements, plus missing perspectives and the list of merged items |
| `roundtrip/write_task.md` | The task given to the writers (20 odd-numbered messages not used in the design) |
| `roundtrip/results.json` | Written messages, the readers' back-translations, and blind grading (Z1 Haiku low effort, Z2 careful (tool-assisted) encoder, Z3 default model) |
| `roundtrip/validity.json` | Share of out-of-dictionary words in the written messages, and token ratios per tokenizer |
| `roundtrip/first_run_invalid.json` | The first run, marked invalid. The Haiku writer answered a question that was passed along with the task instead of doing the task |

The spec given to the writers is `../tokenization/verify/a2_spec_A_conservative.txt`.
