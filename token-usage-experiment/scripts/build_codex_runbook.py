#!/usr/bin/env python3
"""Generate a single self-contained markdown runbook for reproducing this
experiment against OpenAI Codex CLI. Includes every prompt inline plus
scoring rubrics."""
import json
from pathlib import Path

ROOT = Path(__file__).parent
MANIFEST = json.loads((ROOT / "manifest.json").read_text())
INPUTS = ROOT / "inputs"
PROMPTS = ROOT / "prompts"
DEST = Path("/Users/michaelficocelli/work/spin/token-usage-experiment/codex-runbook.md")


TASK_META = [
    ("t1_bugs", "Find bugs in code",
     "Identify and fix bugs in a Python snippet."),
    ("t2_tests", "Unit tests to >90% coverage",
     "Write pytest tests for a Python class covering documented behaviors."),
    ("t3_legal", "Summarize legal snippet",
     "Explain a contract section in plain language and define key legal terms."),
    ("t4_meeting", "Summarize meeting transcript",
     "Bullet the key decisions and action items from a meeting."),
    ("t5_extract", "Extract resume to JSON",
     "Extract structured fields from a resume into a target JSON schema."),
    ("t6_math", "Multi-step arithmetic",
     "Solve a multi-step word problem with a distractor number."),
]

CONDITION_META = [
    ("c1_baseline", "Baseline",
     "Simple, brief task instruction. No shaping."),
    ("c2_detailed", "Detailed instructions",
     "One prescriptive paragraph telling the model exactly how to approach and format the task."),
    ("c3_caveman", "Caveman-speak",
     "Model is told to drop stopwords and grammatical filler and think in the same style."),
    ("c4_html", "HTML output",
     "Baseline plus a request for a full standalone HTML document as the answer."),
    ("c5_rtk", "rtk (CLI compression)",
     "For tasks that use CLI tools, wrap commands with the rtk CLI proxy so command output "
     "is filtered before it reaches the model context. Applied only to T1 and T2."),
    ("c6_hardcap", "Hard output cap",
     "Prepend an instruction to skip preamble and closings, with a hard cap of 150 output tokens."),
    ("c7_spr", "SPR-compressed input",
     "Preprocess the prompt to drop stopwords and collapse whitespace, in the style of "
     "Sparse Priming Representations."),
]


def _load(p: Path) -> str:
    return p.read_text() if p.exists() else "(missing)"


def main():
    out = []
    out.append("# Codex runbook: token-usage experiment\n\n")
    out.append("Self-contained playbook for reproducing a token-usage vs task-success experiment "
               "against OpenAI Codex. Every input, prompt, and scoring rubric is inlined below "
               "so this single markdown file is all you need.\n\n")

    out.append("## What you're producing\n\n")
    out.append("For each of the 38 (task, condition) combinations listed, capture:\n\n")
    out.append("1. The model's full response text.\n")
    out.append("2. Token counts if Codex exposes them: input tokens, output tokens, "
               "and reasoning tokens if any.\n")
    out.append("3. Wall-clock duration of the call.\n\n")
    out.append("Save each response as `outputs/codex/<run_id>.json` in the shape:\n\n")
    out.append('```json\n{"response": "<full response text>", "tokens": {"input": 0, "output": 0, "reasoning": 0}, "duration_ms": 0}\n```\n\n')
    out.append("Return the whole `outputs/codex/` directory. Scoring is automated on our side "
               "against the same rubrics in this document.\n\n")

    out.append("## Getting Codex ready\n\n")
    out.append("Install and authenticate the OpenAI Codex CLI per its docs "
               "(https://github.com/openai/codex). Verify:\n\n")
    out.append("```\ncodex --version\ncodex --help | grep -E '(prompt|model|json)'\n```\n\n")
    out.append("Then confirm a non-interactive call works. The exact flag names may differ across "
               "Codex versions; the common shapes are:\n\n")
    out.append("```\n"
               "# Newer builds\n"
               "codex exec --model gpt-5.4 \"Say only the word: pong\"\n\n"
               "# Older builds\n"
               "codex --prompt \"Say only the word: pong\" --model gpt-5.4\n"
               "```\n\n")
    out.append("Match the model to whatever slot you want compared. Recommended: pick one model "
               "(e.g. `gpt-5.4`) and use it for all 38 runs so the comparison is clean.\n\n")

    out.append("## Runner script (Python)\n\n")
    out.append("Adjust `CODEX_CMD` to your Codex CLI's actual invocation. Everything else can stay "
               "as-is. The script reads the prompts inline from this file (search for a fenced "
               "`text` block whose caption matches `PROMPT: <run_id>`) or you can paste the prompts "
               "into `prompts/<run_id>.txt` first.\n\n")
    out.append("```python\n"
               "import json, re, subprocess, time\n"
               "from pathlib import Path\n\n"
               "PROMPTS = Path('prompts')  # directory with one <run_id>.txt per run\n"
               "OUT = Path('outputs/codex')\n"
               "OUT.mkdir(parents=True, exist_ok=True)\n\n"
               "# Adjust to whatever your Codex build wants. --yolo-equivalent flag if needed.\n"
               "def codex_call(prompt: str) -> dict:\n"
               "    t0 = time.time()\n"
               "    r = subprocess.run(\n"
               "        ['codex', 'exec', '--model', 'gpt-5.4', prompt],\n"
               "        capture_output=True, text=True, timeout=300,\n"
               "    )\n"
               "    dur = int((time.time() - t0) * 1000)\n"
               "    # Strip any trailing session-summary footer your build emits.\n"
               "    lines = (r.stdout or '').splitlines()\n"
               "    keep, footer_re = [], re.compile(r'^(Changes|Requests|Tokens|Session|Model)\\\\s')\n"
               "    for ln in lines:\n"
               "        if footer_re.match(ln): break\n"
               "        keep.append(ln)\n"
               "    while keep and not keep[-1].strip(): keep.pop()\n"
               "    return {'response': '\\n'.join(keep), 'duration_ms': dur,\n"
               "            'tokens': {'input': 0, 'output': 0, 'reasoning': 0}}\n\n"
               "for pf in sorted(PROMPTS.glob('*.txt')):\n"
               "    run_id = pf.stem\n"
               "    out_path = OUT / f'{run_id}.json'\n"
               "    if out_path.exists() and out_path.stat().st_size > 40:\n"
               "        print(f'skip {run_id}'); continue\n"
               "    print(f'run  {run_id}')\n"
               "    data = codex_call(pf.read_text())\n"
               "    out_path.write_text(json.dumps(data, indent=2))\n"
               "```\n\n")
    out.append("If Codex prints token counts to stdout in a machine-readable form, parse them and "
               "fill in the `tokens` dict. Otherwise leave zeros: we can char-estimate on our side.\n\n")

    out.append("## Task inputs\n\n")
    out.append("The six input specimens each prompt is built from. Included for reference only; "
               "the prompts below already have them interpolated.\n\n")
    for tid, label, blurb in TASK_META:
        fname_map = {
            "t1_bugs": "task1_buggy_code.py",
            "t2_tests": "task2_code_for_tests.py",
            "t3_legal": "task3_legal_snippet.md",
            "t4_meeting": "task4_meeting_transcript.md",
            "t5_extract": "task5_resume_snippet.md",
            "t6_math": "task6_word_problem.md",
        }
        content = _load(INPUTS / fname_map[tid])
        out.append(f"### {tid}: {label}\n\n")
        out.append(f"{blurb}\n\n")
        out.append(f"<details><summary>Show input file (<code>{fname_map[tid]}</code>)</summary>\n\n")
        lang = "python" if fname_map[tid].endswith(".py") else "text"
        out.append(f"```{lang}\n{content}\n```\n\n")
        out.append("</details>\n\n")

    out.append("## Conditions\n\n")
    out.append("Each of the 38 runs is a (task, condition) pair. The condition changes how the "
               "prompt is built from the task input.\n\n")
    for cid, label, blurb in CONDITION_META:
        out.append(f"- **{cid} — {label}.** {blurb}\n")
    out.append("\n")

    out.append("## The 38 prompts\n\n")
    out.append("Each block below is the exact text to send as the user message. The heading "
               "gives the `run_id` and the filename `prompts/<run_id>.txt` matches the runner "
               "script above.\n\n")
    applicable = [e for e in MANIFEST if e["applicable"]]
    for entry in applicable:
        rid = entry["run_id"]
        prompt_text = (PROMPTS / f"{rid}.txt").read_text()
        out.append(f"### PROMPT: {rid}\n\n")
        # Fence with a caption-ish first line so users can visually tell prompts apart.
        # Use ``````` (six backticks) to survive any triple-backtick fences the prompt itself
        # might contain (T1/T2 include code blocks).
        out.append(f"``````text\n{prompt_text}\n``````\n\n")

    out.append("## Scoring rubrics\n\n")
    out.append("Each task has an automated rubric. Copy responses back to us and we'll re-run "
               "the scorer, or apply these criteria yourself.\n\n")
    for tid, label, _ in TASK_META:
        rubric_path = INPUTS / f"{tid.split('_')[0]}_ground_truth.md"
        content = _load(rubric_path)
        out.append(f"### Rubric: {tid} — {label}\n\n")
        out.append(f"{content}\n\n")

    out.append("## What to send back\n\n")
    out.append("Any of:\n\n")
    out.append("- The `outputs/codex/` directory with 38 JSON files.\n")
    out.append("- Or a single tar/zip of that directory.\n")
    out.append("- Or paste each response into a shared doc, keyed by `run_id`. Slower but works.\n\n")
    out.append("Include one note per run if anything went sideways (rate-limit, timeout, refusal).\n")

    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text("".join(out))
    print(f"Wrote {DEST} ({DEST.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
