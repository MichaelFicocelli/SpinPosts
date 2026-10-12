# Codex token-usage experiment

The 38 prompts in `runbook.md` were run verbatim with Codex CLI 0.156.1 at low reasoning effort. Each call used an isolated temporary working directory. Runs used three concurrent workers. `rtk` 0.50.0 was installed for the two `c5_rtk` prompts.

| Model | Result directory | Complete runs | Input tokens | Output tokens | Reasoning tokens | Sum of call durations |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| gpt-5.6-terra | `codex/` | 38/38 | 1,049,303 | 28,205 | 6,838 | 701,680 ms |
| gpt-5.6-luna | `codex_gpt-5.6-luna/` | 38/38 | 860,709 | 29,188 | 6,007 | 714,777 ms |

Each result file has the runbook's `response`, `tokens`, and `duration_ms` fields. Token counts are reported by Codex for the entire turn, including its harness and any tool use. The durations above are sums across concurrent calls, not elapsed time for the sweep.

The runbook suggests `gpt-5.4` as one possible model, but this account rejected it with HTTP 400: “The 'gpt-5.4' model is not supported when using Codex with a ChatGPT account.” The 38 failed attempt logs are in `codex_gpt-5.4/`; they are not counted as completed runs.

The runbook's scoring rubric entries are all marked `(missing)`, so no formal task-success scores were computed. One manual check found the expected math answer to be **$58,682**. All six `gpt-5.6-terra` math responses gave that answer; `gpt-5.6-luna` gave a different answer in the baseline, hard-cap, and SPR conditions.
