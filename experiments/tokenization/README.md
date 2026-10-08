# Tokenization experiment (stage 2)

The conclusions and their interpretation are in [docs/02-tokens-and-forms.md](../../docs/02-tokens-and-forms.md). This directory is for reproduction.

## Reproduce

```bash
cd experiments/tokenization
pip install -r requirements.txt
python3 fetch_tokenizers.py   # extracts the 7 tokenizers from PyPI packages into .cache/ (checks SHA-256)
python3 inventory.py          # about 70 s, results/inventory.*
python3 alignment.py          # about 30 s, results/alignment.*
python3 baseline.py           # a few seconds, results/baseline.*
python3 projection.py         # about 30 s, results/projection.*
```

Apart from the `runtime_sec` field, the output is identical on every run.

## Files

| File | Contents |
|---|---|
| `toklib.py` | Common interface to the 7 tokenizers (`count`, `pieces`, `boundaries`, `is_single_token`) |
| `fetch_tokenizers.py` | Downloads the tokenizer files from version-pinned PyPI wheels |
| `inventory.py` | How many forms are single tokens and not words, by shape and spelling |
| `alignment.py` | Agreement between token boundaries and morpheme boundaries, by spelling scheme |
| `baseline.py` | Token counts of the corpus in plain English, terse English, Korean and JSON |
| `projection.py` | Token counts measured after turning the morpheme analyses of the stage-1 draft grammar into real strings |
| `pilot_segmentation.py` | Builds and grades the Claude read/write pilot materials for each spelling scheme |
| `corpus/ai_messages.json` | 40 messages between AI agents (en, en_terse, ko, json) |
| `corpus/gloss_{1,2}.json` | Morpheme analyses made independently by two estimators |
| `results/` | json and md results of each experiment; `pilot/` holds the pilot tasks, answers, gold answers and scores |
| `verify/` | Rebuttal checks: independent reimplementation (`v_*`), two designs that try to beat terse English (KODEX `attempt_1*`, LEAN `a2_*`), generalization to held-out messages (`heldout_*`), Claude reading experiment (`readability/`) |

The large cache files in `verify/` (vocabulary scan results) are not committed to the repository. Each script rebuilds them.
The current Claude tokenizer is not public, so `claude_legacy` (Claude 2-era tokenizer) is used as a proxy.
