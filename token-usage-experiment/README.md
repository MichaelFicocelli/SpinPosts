# Token-usage experiment

Snapshot of a 152-run comparison of prompt conditions across 4 models
(Opus 4.7, Sonnet 4.5, Fable 5.1, GitHub Copilot on GPT-5.4). The full
methodology, per-run details, and interactive tables live in `report.html`.

## What's here

```
report.html                      # Full dark-mode report (open in a browser)
manifest.json                    # Every (task, condition) combination that ran
inputs/                          # 6 task specimens + 6 ground-truth rubrics
prompts/                         # 38 exact prompt files sent to each model
outputs/{opus,sonnet,fable,copilot}/
                                 # One JSON per run with {"response": "..."}.
                                 # Copilot runs also have .usage.json (real
                                 # input/output/reasoning token counts).
scored/results.json              # Auto-scored verdict per run + estimated tokens
scored/summary.json              # Aggregate counts
scripts/build_prompts.py         # Rebuild the 38 prompt files from inputs
scripts/score_outputs.py         # Re-score outputs/ against the rubrics
scripts/build_report.py          # Regenerate report.html
scripts/run_copilot.py           # Re-run the Copilot column
codex-runbook.md                 # Self-contained playbook for a Codex run
```

## Reproducing

To rebuild the prompt files after edits:

```
python3 scripts/build_prompts.py
```

To re-score after new outputs land:

```
python3 scripts/score_outputs.py
```

To regenerate the report:

```
python3 scripts/build_report.py
```

To add a new model column, drop its outputs into `outputs/<model>/<run_id>.json`
using the same `{"response": "..."}` shape, add the model name to `MODELS` in
`score_outputs.py` and `MODELS_ORDER` (with a label and a color) in
`build_report.py`, then re-run the scoring and report scripts.

## Handing this to a coworker for a Codex run

Give them `codex-runbook.md`. It embeds every prompt and every rubric, plus
a copy-paste runner script. They send back their outputs directory and this
folder can be re-scored and re-rendered without further coordination.
