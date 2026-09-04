#!/usr/bin/env python3
"""Generate all (task x condition) prompt files from specimens.

Also builds a manifest.json listing every run (task, condition, applicable? flag).
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
INPUTS = ROOT / "inputs"
PROMPTS = ROOT / "prompts"
PROMPTS.mkdir(exist_ok=True)


# ---- Task specifications: id, label, base-task-prompt (no condition wrapping), input file ----
TASKS = [
    {
        "id": "t1_bugs",
        "label": "Find bugs in code",
        "input": "task1_buggy_code.py",
        "base_instruction": (
            "The following Python code has one or more subtle bugs. "
            "Identify the bug(s) and propose a specific fix for each. "
            "Code:\n\n{content}"
        ),
        "detailed_instruction": (
            "You are reviewing Python code for correctness. Read every function carefully. "
            "For EACH bug: (1) name the function it lives in, (2) quote the exact line or "
            "expression that is wrong, (3) explain why it is wrong in one sentence, and "
            "(4) show the specific code change that fixes it. Check for off-by-one errors, "
            "wrong sort order, missing edge cases, and any place a docstring or function "
            "name contradicts what the code actually does. Do not invent bugs that are not "
            "real. Code:\n\n{content}"
        ),
    },
    {
        "id": "t2_tests",
        "label": "Write unit tests to >90% coverage",
        "input": "task2_code_for_tests.py",
        "base_instruction": (
            "Write unit tests for the following Python class that would achieve >90% branch "
            "coverage. Use pytest style. Code:\n\n{content}"
        ),
        "detailed_instruction": (
            "Write a pytest-style test suite for the following Python class targeting >90% "
            "branch coverage. Enumerate every documented rule (grace period, minimum fee, "
            "maximum cap, weekend exclusion, rounding, non-positive balance short-circuit, "
            "and the `today` injection). Write ONE test per rule with a clearly-named "
            "function (e.g. test_returns_zero_when_balance_is_zero). Use small, deterministic "
            "date fixtures. Do not test private helpers directly if you can hit them through "
            "the public API. Code:\n\n{content}"
        ),
    },
    {
        "id": "t3_legal",
        "label": "Summarize legal snippet for layperson",
        "input": "task3_legal_snippet.md",
        "base_instruction": (
            "Summarize the following contract section for a non-technical reader, and define "
            "the key legal terms in plain language.\n\n{content}"
        ),
        "detailed_instruction": (
            "You are explaining a contract section to a business owner with no legal "
            "training. Do two things: (1) In 5-8 short bullet points, translate what the "
            "section actually requires each party to do, and when the promises do or do not "
            "apply. Include the dollar cap and its exceptions. (2) Then, in a 'Key terms' "
            "glossary, define each of the following in one plain sentence: indemnify / hold "
            "harmless, third-party claim, gross negligence vs. willful misconduct, "
            "intellectual property infringement or misappropriation, consequential / "
            "incidental / punitive damages, cap on liability, sole control of the defense, "
            "materially prejudiced. Avoid legalese; use everyday words.\n\n{content}"
        ),
    },
    {
        "id": "t4_meeting",
        "label": "Summarize meeting transcript",
        "input": "task4_meeting_transcript.md",
        "base_instruction": (
            "Summarize the following meeting transcript as bullet points covering the key "
            "decisions/points and the next steps / action items.\n\n{content}"
        ),
        "detailed_instruction": (
            "Produce a structured summary of the following meeting transcript. Include: "
            "(1) 'Key points' — bullet list of every decision made or major discussion "
            "outcome, one line each. (2) 'Action items' — bullet list of every commitment, "
            "in the form 'Owner: what, by when'. Include the anchor decisions on "
            "reconciliation, the mobile receipt-capture scope call, the vendor payout SLA "
            "plan, the Q4 push of audit-log retention, and the on-call rotation ask. Do not "
            "include chit-chat or restate the transcript.\n\n{content}"
        ),
    },
    {
        "id": "t5_extract",
        "label": "Extract resume to JSON",
        "input": "task5_resume_snippet.md",
        "base_instruction": (
            "Extract information from the following resume into a JSON object with fields: "
            "name (string), years_experience (integer), skills (array of strings), "
            "most_recent_role (object with title, company, dates). Respond with only the "
            "JSON object.\n\nResume:\n\n{content}"
        ),
        "detailed_instruction": (
            "Extract the following fields from this resume into a single JSON object. "
            "Rules: 'name' is the person's full name as written; 'years_experience' is the "
            "single integer count of years of professional experience stated in the summary "
            "(not computed from dates); 'skills' is a de-duplicated flat array of the "
            "skill strings listed in the Skills section, preserving order; 'most_recent_role' "
            "is the CURRENTLY-HELD role (dates end with 'present') with keys 'title', "
            "'company', and 'dates'. Respond with ONLY the JSON object, no code fences or "
            "commentary.\n\nResume:\n\n{content}"
        ),
    },
    {
        "id": "t6_math",
        "label": "Multi-step arithmetic word problem",
        "input": "task6_word_problem.md",
        "base_instruction": (
            "Solve the following word problem. Show your work and give a final numeric "
            "answer.\n\n{content}"
        ),
        "detailed_instruction": (
            "Solve this word problem step by step. Enumerate: (1) base fees per case type, "
            "(2) subtotal, (3) surcharge applied, (4) electronic-filing credits per case "
            "type and total credit, (5) net collected, (6) the courthouse's 82% share. "
            "Watch for irrelevant numbers explicitly stated to be out of scope. Give the "
            "final answer as a single dollar figure rounded to the nearest dollar on its "
            "own line, prefixed 'FINAL:'.\n\n{content}"
        ),
    },
]


# ---- Condition modifiers ----
def cond_baseline(base_prompt: str, task: dict) -> str:
    return base_prompt


def cond_detailed(base_prompt: str, task: dict) -> str:
    # Use the pre-written detailed variant, filled with the content
    return task["_detailed_prompt"]


def cond_caveman(base_prompt: str, task: dict) -> str:
    preface = (
        "CAVEMAN MODE. Talk caveman. Drop 'the', 'a', 'is', 'are', 'that', 'to', 'of' "
        "when meaning still clear. Short words. Grunt-style. THINK in caveman too, "
        "not just output. Save word. Save token. Still solve task correctly.\n\n"
        "TASK:\n"
    )
    return preface + base_prompt


def cond_html(base_prompt: str, task: dict) -> str:
    return (
        base_prompt
        + "\n\nRespond with a complete standalone HTML document (with <!doctype html>, "
        "<head>, <style>, <body>) that presents the task and your answer clearly."
    )


def cond_rtk(base_prompt: str, task: dict) -> str:
    # rtk (github.com/rtk-ai/rtk) is a CLI proxy that filters/compresses common
    # command output before it reaches the model context. Only applicable to
    # tasks where the agent gathers signal from CLI tools.
    code = base_prompt.split("Code:\n\n", 1)[-1]
    if task["id"] == "t1_bugs":
        return (
            "You have access to Bash and the `rtk` CLI (github.com/rtk-ai/rtk). "
            "Save the code below to $TMPDIR/target.py. Use rtk-wrapped commands "
            "wherever you would otherwise use raw shell output as evidence:\n"
            "  * `rtk read -l aggressive $TMPDIR/target.py` to look at the code again if needed.\n"
            "  * `rtk err python3 -m py_compile $TMPDIR/target.py` for syntax checks.\n"
            "  * `rtk grep <pattern> $TMPDIR/target.py` to locate constructs.\n"
            "Then identify the bug(s) and propose specific fixes.\n\nCode:\n\n" + code
        )
    if task["id"] == "t2_tests":
        return (
            "You have access to Bash and the `rtk` CLI (github.com/rtk-ai/rtk). "
            "Save the code below to $TMPDIR/target.py. Use rtk-wrapped commands "
            "wherever you would otherwise use raw shell output:\n"
            "  * `rtk read -l aggressive $TMPDIR/target.py` for a compact view.\n"
            "  * `rtk grep 'def ' $TMPDIR/target.py` to enumerate methods.\n"
            "  * `rtk err python3 -m py_compile $TMPDIR/target.py` to confirm the file parses.\n"
            "Then write pytest tests targeting >90% branch coverage.\n\nCode:\n\n" + code
        )
    return None  # N/A


def cond_hardcap(base_prompt: str, task: dict) -> str:
    preface = (
        "OUTPUT CONSTRAINTS: Respond in the minimum tokens possible. No preamble, no "
        "disclaimers, no restating the task, no closing remarks. Hard cap: 150 output "
        "tokens. Use terse bullets, short phrases, or JSON as fits the task.\n\n"
    )
    return preface + base_prompt


# --- SPR-style input compression ---
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "of", "in", "on", "at", "to", "for",
    "with", "as", "by", "is", "are", "was", "were", "be", "been", "being",
    "that", "this", "these", "those", "it", "its", "into", "from", "such",
    "any", "all", "each", "some", "very", "more", "most", "than", "then",
    "so", "if", "when", "while", "which", "who", "whom", "whose", "would",
    "could", "should", "may", "might", "shall", "will", "have", "has", "had",
    "do", "does", "did", "not", "no", "just", "also", "over",
}


def compress_prose(text: str) -> str:
    """Compress prose paragraphs: strip stopwords, collapse whitespace, shorten
    common phrases. Preserve code blocks and lines that look like code."""
    lines = text.split("\n")
    out_lines = []
    in_code = False
    for line in lines:
        stripped = line.strip()
        # detect fenced code
        if stripped.startswith("```"):
            in_code = not in_code
            out_lines.append(line)
            continue
        # keep code-like lines intact
        looks_like_code = (
            in_code
            or line.startswith(" " * 4)
            or line.startswith("\t")
            or bool(re.match(r"^(def |class |import |from |return |if |for |while |#|@|\s*[a-zA-Z_]+\s*=)", line))
        )
        if looks_like_code:
            out_lines.append(line)
            continue
        # heading? keep it
        if stripped.startswith("#") or stripped.startswith("*") or stripped.startswith("-"):
            # still compress the content after the marker
            marker, _, rest = stripped.partition(" ")
            compressed = _drop_stopwords(rest)
            out_lines.append(f"{marker} {compressed}")
            continue
        out_lines.append(_drop_stopwords(stripped))
    result = "\n".join(out_lines)
    # collapse multiple blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result


def _drop_stopwords(text: str) -> str:
    tokens = re.findall(r"\w+|[^\w\s]", text)
    kept = []
    for t in tokens:
        if t.lower() in STOPWORDS and re.match(r"\w+", t):
            continue
        kept.append(t)
    # re-join with spaces, but no space before punctuation
    out = ""
    for t in kept:
        if re.match(r"[^\w\s]", t):
            out += t
        else:
            if out and not out.endswith(" ") and not out.endswith("\n"):
                out += " "
            out += t
    return out


def cond_spr(base_prompt: str, task: dict) -> str:
    # Compress everything, then add a tiny header saying the input has been compressed
    header = "INPUT IS SPR-COMPRESSED (stopwords stripped, prose condensed). Interpret charitably.\n\n"
    return header + compress_prose(base_prompt)


CONDITIONS = [
    ("c1_baseline", "Baseline", cond_baseline),
    ("c2_detailed", "Detailed instructions", cond_detailed),
    ("c3_caveman", "Caveman-speak", cond_caveman),
    ("c4_html", "HTML output", cond_html),
    ("c5_rtk", "rtk (CLI compression)", cond_rtk),
    ("c6_hardcap", "Hard output cap", cond_hardcap),
    ("c7_spr", "SPR-compressed input", cond_spr),
]


def main():
    manifest = []
    for task in TASKS:
        input_file = INPUTS / task["input"]
        content = input_file.read_text()
        base_prompt = task["base_instruction"].format(content=content)
        task["_detailed_prompt"] = task["detailed_instruction"].format(content=content)

        for cond_id, cond_label, fn in CONDITIONS:
            prompt = fn(base_prompt, task)
            applicable = prompt is not None
            entry = {
                "run_id": f"{task['id']}__{cond_id}",
                "task_id": task["id"],
                "task_label": task["label"],
                "condition_id": cond_id,
                "condition_label": cond_label,
                "applicable": applicable,
            }
            if applicable:
                prompt_path = PROMPTS / f"{entry['run_id']}.txt"
                prompt_path.write_text(prompt)
                entry["prompt_file"] = str(prompt_path)
                entry["prompt_chars"] = len(prompt)
                entry["prompt_tokens_est"] = round(len(prompt) / 4)
            else:
                entry["skip_reason"] = "rtk not meaningful for this task (no CLI to compress)"
            manifest.append(entry)

    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    n_applicable = sum(1 for m in manifest if m["applicable"])
    print(f"Wrote {n_applicable} prompt files (of {len(manifest)} total combos).")
    print(f"Per model: {n_applicable} runs. Across 3 models: {n_applicable * 3} total runs.")


if __name__ == "__main__":
    main()
