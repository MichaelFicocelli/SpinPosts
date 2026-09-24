# Run notes — token-usage experiment

## Substitution: Codex -> Claude CLI
The OpenAI Codex CLI is not installed on this machine (`codex: command not found`),
so all runs were executed against the `claude` CLI (v2.1.278) instead, per instruction
to run the experiment anyway. Two models, all runs each:

- `outputs/codex_sonnet/` — claude-sonnet-5
- `outputs/codex_opus/`   — claude-opus-5

Invocation (prompt on stdin):

    claude -p --output-format json --model <model> \
      --system-prompt "You are a helpful assistant." \
      --strict-mcp-config --exclude-dynamic-system-prompt-sections \
      --disallowed-tools Bash Read Write Edit Glob Grep WebFetch WebSearch Task NotebookEdit TodoWrite

Tools were disabled and the agent system prompt replaced with a minimal one so each
run is a single-shot generation rather than agentic work.

## Scope: rtk skipped
c5_rtk (t1_bugs__c5_rtk, t2_tests__c5_rtk) was skipped as instructed.
**36 of 38 runs per model; 72 JSON files total.** No other runs were omitted.

## Token accounting caveats — READ BEFORE SCORING INPUT TOKENS
1. `tokens.input` = input_tokens + cache_creation_input_tokens + cache_read_input_tokens.
2. It includes a **fixed harness overhead of ~16,037 tokens** (CLI system prompt +
   tool schemas), measured with a 2-token control prompt. Subtract it to approximate
   prompt-only input. This overhead swamps the input-size differences that c7_spr is
   meant to test, so **use `prompt_chars` (exact, per run) as the input-size measure**,
   not `tokens.input`.
3. A few runs took more than one internal iteration; their `tokens.input` double-counts
   the cached prefix. Outputs are unaffected.
4. `tokens.output` and `tokens.reasoning` (extended-thinking tokens) are clean and
   directly comparable across conditions.
5. `duration_ms` is the CLI-reported wall clock for the call.

## Failures
None. 72/72 runs returned non-empty responses, no timeouts, rate limits, refusals,
or API errors. First attempt at the batch failed on a CLI arg-parsing bug (the
variadic `--disallowed-tools` swallowed the positional prompt); fixed by piping the
prompt on stdin and the whole batch was re-run clean.

## Extras included
- `summary.csv` — one row per run: model, task, condition, prompt_chars, input/output/
  reasoning tokens, response_chars, duration_ms.
- `prompts/` — the 36 exact prompt files used.
- `inputs/`, `spr/` — the six task specimens and the six SPR-compressed variants.
- `run.py`, `build_prompts.py`, `summarize.py` — the runner and support scripts.
- Only t6_math has a deterministic answer, so it is the one thing scored locally:
  ground truth $58,682 (69,300 -> x1.06 = 73,458; e-file credits 1,895; net 71,563;
  x0.82 = 58,681.66). **12/12 runs correct across both models and all six conditions**,
  including c6_hardcap and c7_spr. The $9,400 passport distractor was not taken by any run.
  t1-t5 rubrics were "(missing)" in the runbook, so those are left for your scorer.
