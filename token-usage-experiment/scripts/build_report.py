#!/usr/bin/env python3
"""Build a dark-mode HTML report from scored/results.json.

Sections:
- Executive summary (total runs, success rate, token savings by condition)
- Methodology
- Overview chart: token usage by condition, grouped by model (bar)
- Overview chart: success rate by condition, grouped by model (bar)
- Per-task detail: table of runs (model x condition) with tokens + verdict
- Per-run detail: expandable rows showing the prompt and full response

Uses inline SVG for charts (no external JS). Uses inline CSS.
"""
import json
import html
import re
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).parent
SCORED = ROOT / "scored"
RESULTS = json.loads((SCORED / "results.json").read_text())
MANIFEST = json.loads((ROOT / "manifest.json").read_text())

TASKS_ORDER = ["t1_bugs", "t2_tests", "t3_legal", "t4_meeting", "t5_extract", "t6_math"]
CONDITIONS_ORDER = ["c1_baseline", "c2_detailed", "c3_caveman", "c4_html", "c5_rtk", "c6_hardcap", "c7_spr"]
MODELS_ORDER = ["opus", "sonnet", "fable", "copilot"]

TASK_LABELS = {
    "t1_bugs": "T1. Find bugs in code",
    "t2_tests": "T2. Unit tests to >90% coverage",
    "t3_legal": "T3. Summarize legal snippet",
    "t4_meeting": "T4. Summarize meeting transcript",
    "t5_extract": "T5. Extract resume to JSON",
    "t6_math": "T6. Multi-step arithmetic",
}
COND_LABELS = {
    "c1_baseline": "Baseline",
    "c2_detailed": "Detailed instructions",
    "c3_caveman": "Caveman-speak",
    "c4_html": "HTML output",
    "c5_rtk": "rtk (CLI compression)",
    "c6_hardcap": "Hard output cap",
    "c7_spr": "SPR-compressed input",
}
MODEL_LABELS = {"opus": "Opus 4.7", "sonnet": "Sonnet 4.5", "fable": "Fable 5.1", "copilot": "Copilot (GPT-5.4)"}

VERDICT_COLORS = {"success": "#4ade80", "partial": "#fbbf24", "fail": "#f87171", "missing": "#6b7280"}
MODEL_COLORS = {"opus": "#a78bfa", "sonnet": "#38bdf8", "fable": "#f472b6", "copilot": "#34d399"}


def by(key, iterable):
    out = {}
    for x in iterable:
        out.setdefault(x[key], []).append(x)
    return out


def esc(s):
    return html.escape(str(s), quote=False)


# ---- SVG bar chart helpers ----
def bar_chart_grouped(data, labels, group_labels, title, y_label, colors, height=280, bar_w=18, gap=6, group_gap=22, max_y=None):
    """data: {group_label: [values matching labels]}. Returns SVG string."""
    n_labels = len(labels)
    n_groups = len(group_labels)
    group_width = n_groups * bar_w + (n_groups - 1) * gap
    label_slot = group_width + group_gap
    left_pad = 60
    right_pad = 20
    top_pad = 40
    bot_pad = 90
    plot_h = height - top_pad - bot_pad
    if max_y is None:
        max_y = max((v for arr in data.values() for v in arr), default=1) * 1.1 or 1
    width = left_pad + right_pad + n_labels * label_slot
    parts = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" class="chart">']
    parts.append(f'<text x="{width/2}" y="20" text-anchor="middle" fill="#e5e7eb" font-size="14" font-weight="600">{esc(title)}</text>')
    # y-axis grid
    for frac in [0, 0.25, 0.5, 0.75, 1.0]:
        y = top_pad + plot_h * (1 - frac)
        v = max_y * frac
        parts.append(f'<line x1="{left_pad}" y1="{y}" x2="{width - right_pad}" y2="{y}" stroke="#374151" stroke-width="0.5"/>')
        parts.append(f'<text x="{left_pad - 6}" y="{y + 4}" text-anchor="end" fill="#9ca3af" font-size="10">{v:,.0f}</text>')
    # y-axis label
    parts.append(f'<text x="15" y="{top_pad + plot_h/2}" transform="rotate(-90 15 {top_pad + plot_h/2})" text-anchor="middle" fill="#9ca3af" font-size="11">{esc(y_label)}</text>')
    # bars
    for li, lbl in enumerate(labels):
        x0 = left_pad + li * label_slot + group_gap / 2
        for gi, g in enumerate(group_labels):
            v = data.get(g, [0]*n_labels)[li] if li < len(data.get(g, [])) else 0
            bh = 0 if max_y == 0 else plot_h * (v / max_y)
            bx = x0 + gi * (bar_w + gap)
            by_ = top_pad + plot_h - bh
            color = colors.get(g, "#888")
            parts.append(f'<rect x="{bx}" y="{by_}" width="{bar_w}" height="{bh}" fill="{color}" opacity="0.85"><title>{esc(g)}: {v:,.0f}</title></rect>')
            if v > 0:
                parts.append(f'<text x="{bx + bar_w/2}" y="{by_ - 2}" text-anchor="middle" fill="#e5e7eb" font-size="8">{v:,.0f}</text>')
        # x-axis label (rotated)
        cx = x0 + group_width / 2
        parts.append(f'<text x="{cx}" y="{top_pad + plot_h + 14}" transform="rotate(-30 {cx} {top_pad + plot_h + 14})" text-anchor="end" fill="#d1d5db" font-size="10">{esc(lbl)}</text>')
    # legend
    legend_y = height - 30
    lx = left_pad
    for g in group_labels:
        color = colors.get(g, "#888")
        parts.append(f'<rect x="{lx}" y="{legend_y}" width="12" height="12" fill="{color}"/>')
        parts.append(f'<text x="{lx + 16}" y="{legend_y + 10}" fill="#e5e7eb" font-size="11">{esc(g)}</text>')
        lx += 100
    parts.append('</svg>')
    return "\n".join(parts)


def summarize_by_condition(model_filter=None):
    """Return {condition_id: {'avg_prompt': int, 'avg_response': int, 'avg_total': int, 'success': int, 'partial': int, 'fail': int, 'runs': int}}"""
    out = {}
    for cond_id in CONDITIONS_ORDER:
        rows = [r for r in RESULTS if r["condition_id"] == cond_id and (model_filter is None or r["model"] == model_filter)]
        if not rows:
            continue
        out[cond_id] = {
            "avg_prompt": round(mean(r["prompt_tokens_est"] for r in rows)) if rows else 0,
            "avg_response": round(mean(r["response_tokens_est"] for r in rows)) if rows else 0,
            "avg_total": round(mean(r["total_tokens_est"] for r in rows)) if rows else 0,
            "success": sum(1 for r in rows if r["verdict"] == "success"),
            "partial": sum(1 for r in rows if r["verdict"] == "partial"),
            "fail": sum(1 for r in rows if r["verdict"] == "fail"),
            "runs": len(rows),
        }
    return out


def render_run_detail(run):
    """Return HTML for one run's expandable detail."""
    prompt_text = Path([m for m in MANIFEST if m["run_id"] == run["run_id"]][0]["prompt_file"]).read_text()
    return f"""
    <details class="run-detail">
        <summary>
            <span class="model-chip {run['model']}">{esc(MODEL_LABELS[run['model']])}</span>
            <span class="cond">{esc(COND_LABELS[run['condition_id']])}</span>
            <span class="verdict verdict-{run['verdict']}">{run['verdict'].upper()}</span>
            <span class="tokens">{run['total_tokens_est']:,} tok</span>
        </summary>
        <div class="run-inner">
            <div class="run-meta">
                <span>prompt: {run['prompt_tokens_est']:,} tok ({run['prompt_chars']:,} chars)</span>
                <span>response: {run['response_tokens_est']:,} tok ({run['response_chars']:,} chars)</span>
                <span class="rat">{esc(run['rationale'])}</span>
            </div>
            <h5>Prompt sent to model</h5>
            <pre class="prompt">{esc(prompt_text)}</pre>
            <h5>Model response</h5>
            <pre class="response">{esc(run['response']) if run['response'] else '(no output)'}</pre>
        </div>
    </details>
    """


def render_task_table(task_id):
    """Render a table: rows = conditions, cols = models, cell = tokens + verdict pill."""
    rows_by_cond = {c: {} for c in CONDITIONS_ORDER}
    for r in RESULTS:
        if r["task_id"] != task_id:
            continue
        rows_by_cond.setdefault(r["condition_id"], {})[r["model"]] = r

    parts = ['<table class="matrix"><thead><tr><th>Condition</th>']
    for m in MODELS_ORDER:
        parts.append(f'<th>{esc(MODEL_LABELS[m])}</th>')
    parts.append('</tr></thead><tbody>')
    for cond_id in CONDITIONS_ORDER:
        row = rows_by_cond.get(cond_id, {})
        if not row:
            continue
        parts.append(f'<tr><th>{esc(COND_LABELS[cond_id])}</th>')
        for m in MODELS_ORDER:
            cell = row.get(m)
            if not cell:
                parts.append('<td class="na">n/a</td>')
                continue
            v = cell["verdict"]
            parts.append(f'<td class="cell v-{v}"><span class="v-pill">{v[0].upper()}</span> <span class="tok">{cell["total_tokens_est"]:,}</span></td>')
        parts.append('</tr>')
    parts.append('</tbody></table>')
    return "\n".join(parts)


def render_condition_summary():
    """Per condition, per model: avg tokens, savings vs baseline, success%."""
    # Compute per-(condition, model) averages, plus per-model baseline
    baseline_by_model = {}
    for m in MODELS_ORDER:
        rows = [r for r in RESULTS if r["condition_id"] == "c1_baseline" and r["model"] == m]
        if rows:
            baseline_by_model[m] = round(mean(r["total_tokens_est"] for r in rows))
        else:
            baseline_by_model[m] = 0

    def score_pct(rows):
        if not rows: return None
        return round((sum(1 for r in rows if r["verdict"] == "success") + sum(0.5 for r in rows if r["verdict"] == "partial")) / len(rows) * 100)

    parts = ['<h4>Condition impact summary</h4>']
    parts.append('<table class="matrix summary-table"><thead><tr><th rowspan="2">Condition</th>')
    for m in MODELS_ORDER:
        parts.append(f'<th colspan="3">{esc(MODEL_LABELS[m])}</th>')
    parts.append('</tr><tr>')
    for _ in MODELS_ORDER:
        parts.append('<th>avg tok</th><th>vs base</th><th>score</th>')
    parts.append('</tr></thead><tbody>')

    for cond_id in CONDITIONS_ORDER:
        parts.append(f'<tr><th>{esc(COND_LABELS[cond_id])}</th>')
        for m in MODELS_ORDER:
            rows = [r for r in RESULTS if r["condition_id"] == cond_id and r["model"] == m]
            if not rows:
                parts.append('<td class="na">n/a</td><td class="na">n/a</td><td class="na">n/a</td>')
                continue
            avg = round(mean(r["total_tokens_est"] for r in rows))
            base = baseline_by_model.get(m, 0)
            if cond_id == "c1_baseline":
                vs = '<span class="tok">baseline</span>'
            elif base == 0:
                vs = '<span class="tok">n/a</span>'
            else:
                pct = round((avg - base) / base * 100)
                color = '#4ade80' if pct <= -10 else ('#fbbf24' if pct < 25 else '#f87171')
                sign = '+' if pct > 0 else ''
                vs = f'<span style="color:{color};font-weight:600">{sign}{pct}%</span>'
            pct_score = score_pct(rows)
            score_color = '#4ade80' if (pct_score or 0) >= 90 else ('#fbbf24' if (pct_score or 0) >= 70 else '#f87171')
            parts.append(f'<td>{avg:,}</td><td>{vs}</td><td><span style="color:{score_color};font-weight:600">{pct_score}%</span></td>')
        parts.append('</tr>')
    parts.append('</tbody></table>')
    parts.append('<p class="caveat" style="color:#94a3b8;font-size:12px;margin:8px 0 12px">'
                 'avg tok = average prompt+response tokens per run (chars÷4 estimate). '
                 'vs base = change from baseline for that model. '
                 'score = success × 100% + partial × 50%, averaged over that condition\'s runs (4-6 tasks depending on rtk applicability). '
                 'Green cells: big token savings or high task-success. Yellow: neutral. Red: costly or low task-success.</p>')
    return "\n".join(parts)


RUNNER_TEMPLATE = """Single experimental run. Do NOT explore, plan, or narrate.

1. Read this prompt file: <PROMPT_PATH>
2. Answer that prompt exactly as written, using only your own reasoning
   (no other tool calls needed).
3. Write your response to: <OUTPUT_PATH>
   The file must be valid JSON: {"response": "<your full response as string>"}
4. Return only the text: DONE

The rtk condition additionally instructs the sub-agent to invoke the local
`rtk` binary for its bash calls (rtk read, rtk grep, rtk err).
"""


REPRO_NOTES = """To run this experiment against any provider (OpenAI, Google, Mistral, local models):
send each prompt file below to the model as the user message with an empty
or minimal system prompt, capture the full response text, and score it against
the rubric for that task. The tasks that ship JSON output (T5) should be scored
by parsing the JSON. The one arithmetic task (T6) should be scored by extracting
the final dollar figure. See scored/results.json in the experiment folder for the
exact rubric-check logic used here.
"""


def _load_input(fname: str) -> str:
    p = ROOT / "inputs" / fname
    return p.read_text() if p.exists() else "(input file missing)"


TASK_INPUTS = {
    "t1_bugs": ("task1_buggy_code.py", "Python code snippet with subtle bugs"),
    "t2_tests": ("task2_code_for_tests.py", "Python class to write tests against"),
    "t3_legal": ("task3_legal_snippet.md", "Legal clause"),
    "t4_meeting": ("task4_meeting_transcript.md", "Meeting transcript"),
    "t5_extract": ("task5_resume_snippet.md", "Resume snippet"),
    "t6_math": ("task6_word_problem.md", "Word problem"),
}


TASK_BASE_INSTRUCTIONS = {
    "t1_bugs": (
        "The following Python code has one or more subtle bugs. "
        "Identify the bug(s) and propose a specific fix for each. Code:\n\n{content}"
    ),
    "t2_tests": (
        "Write unit tests for the following Python class that would achieve >90% branch "
        "coverage. Use pytest style. Code:\n\n{content}"
    ),
    "t3_legal": (
        "Summarize the following contract section for a non-technical reader, and define "
        "the key legal terms in plain language.\n\n{content}"
    ),
    "t4_meeting": (
        "Summarize the following meeting transcript as bullet points covering the key "
        "decisions/points and the next steps / action items.\n\n{content}"
    ),
    "t5_extract": (
        "Extract information from the following resume into a JSON object with fields: "
        "name (string), years_experience (integer), skills (array of strings), "
        "most_recent_role (object with title, company, dates). Respond with only the "
        "JSON object.\n\nResume:\n\n{content}"
    ),
    "t6_math": (
        "Solve the following word problem. Show your work and give a final numeric "
        "answer.\n\n{content}"
    ),
}


CONDITION_RECIPES = [
    ("c1_baseline", "Baseline", "Send the task's base instruction verbatim."),
    ("c2_detailed", "Detailed instructions",
     "Replace the base instruction with a prescriptive paragraph tailored to the task. "
     "The paragraph enumerates every rule the model should follow (e.g. \"quote the exact "
     "line\", \"list every documented rule\", \"give the final answer prefixed FINAL:\")."),
    ("c3_caveman", "Caveman-speak",
     "Prepend: \"CAVEMAN MODE. Talk caveman. Drop 'the', 'a', 'is', 'are', 'that', 'to', "
     "'of' when meaning still clear. Short words. Grunt-style. THINK in caveman too, not "
     "just output. Save word. Save token. Still solve task correctly.\" Followed by the "
     "unmodified base instruction."),
    ("c4_html", "HTML output",
     "Append: \"Respond with a complete standalone HTML document (with <!doctype html>, "
     "<head>, <style>, <body>) that presents the task and your answer clearly.\""),
    ("c5_rtk", "rtk (CLI compression)",
     "For task 1 and task 2 only: replace the base with a variant that instructs the "
     "model to save the code to a temp file and then use the `rtk` CLI subcommands "
     "(rtk read, rtk err, rtk grep) for any command-line inspection. Skipped on the "
     "other four tasks."),
    ("c6_hardcap", "Hard output cap",
     "Prepend: \"OUTPUT CONSTRAINTS: Respond in the minimum tokens possible. No preamble, "
     "no disclaimers, no restating the task, no closing remarks. Hard cap: 150 output "
     "tokens. Use terse bullets, short phrases, or JSON as fits the task.\""),
    ("c7_spr", "SPR-compressed input",
     "Preprocess the base prompt: strip common stopwords (\"the\", \"a\", \"of\", \"in\", "
     "\"to\", ...), collapse whitespace, keep code and heading lines intact. Prepend a "
     "header telling the model the input is SPR-compressed so it interprets charitably."),
]


def render_reproduction():
    """Show every prompt component so the experiment can be run against any model."""
    parts = ['<section class="repro"><h2>Reproducing this experiment</h2>']
    parts.append('<p>Every prompt sent to the models is derived from three pieces: '
                 'the task input file, a base task instruction, and a condition modifier. '
                 'All three are shown in full below. The runner template (the sub-agent driver) '
                 'is also shown so it can be adapted to other harnesses.</p>')

    parts.append('<h3>Sub-agent runner template</h3>')
    parts.append('<p>Each of the 114 runs was driven by an isolated Claude Code sub-agent '
                 'with a <code>model</code> override (Opus, Sonnet, Fable). The driver prompt:</p>')
    parts.append(f'<pre class="prompt">{esc(RUNNER_TEMPLATE)}</pre>')

    parts.append('<h3>Task input files</h3>')
    parts.append('<p>Six input files provide the raw content each task operates on:</p>')
    for tid, (fname, desc) in TASK_INPUTS.items():
        content = _load_input(fname)
        parts.append(f'<details class="repro-item"><summary>'
                     f'<strong>{esc(tid)}</strong> &middot; <code>{esc(fname)}</code> &middot; '
                     f'<span class="tok">{esc(desc)}</span></summary>'
                     f'<pre class="prompt">{esc(content)}</pre></details>')

    parts.append('<h3>Base task instructions</h3>')
    parts.append('<p>Under the baseline condition, the prompt sent to the model is the task\'s '
                 'base instruction with the input file content interpolated where '
                 '<code>{content}</code> appears:</p>')
    for tid, instruction in TASK_BASE_INSTRUCTIONS.items():
        parts.append(f'<details class="repro-item"><summary>'
                     f'<strong>{esc(tid)}</strong> base instruction</summary>'
                     f'<pre class="prompt">{esc(instruction)}</pre></details>')

    parts.append('<h3>Condition modifiers</h3>')
    parts.append('<p>Each condition transforms the base prompt in a specific way. '
                 'The transformation for each condition:</p>')
    for cid, label, recipe in CONDITION_RECIPES:
        parts.append(f'<details class="repro-item"><summary>'
                     f'<strong>{esc(cid)}</strong> &middot; {esc(label)}</summary>'
                     f'<p>{esc(recipe)}</p></details>')

    parts.append('<h3>Every prompt as sent</h3>')
    parts.append('<p>The 38 fully-composed prompt files (one per applicable task-by-condition combination) '
                 'are stored under <code>prompts/&lt;task_id&gt;__&lt;condition_id&gt;.txt</code> '
                 'in the experiment folder. They also appear inline under each per-run detail '
                 'below (in the Per-task results section, expand a run to see its prompt and response verbatim).</p>')

    parts.append('<h3>Running against a different provider</h3>')
    parts.append(f'<p>{esc(REPRO_NOTES)}</p>')
    parts.append('<p>Example (OpenAI Python SDK):</p>')
    parts.append('<pre class="prompt">'
                 'import json, openai\n'
                 'client = openai.OpenAI()\n'
                 'prompt = open("prompts/t1_bugs__c1_baseline.txt").read()\n'
                 'r = client.chat.completions.create(\n'
                 '    model="gpt-5",\n'
                 '    messages=[{"role": "user", "content": prompt}],\n'
                 ')\n'
                 'response_text = r.choices[0].message.content\n'
                 'usage = r.usage  # input_tokens, output_tokens\n'
                 'json.dump({"response": response_text}, open("outputs/openai/t1_bugs__c1_baseline.json", "w"))'
                 '</pre>')

    parts.append('</section>')
    return "\n".join(parts)


def render_task_section(task_id):
    task_runs = [r for r in RESULTS if r["task_id"] == task_id]
    return f"""
    <section class="task-section" id="task-{task_id}">
        <h3>{esc(TASK_LABELS[task_id])}</h3>
        {render_task_table(task_id)}
        <details class="all-runs"><summary>Per-run details ({len(task_runs)} runs, click to expand)</summary>
        <div class="runs-list">
        {"".join(render_run_detail(r) for r in sorted(task_runs, key=lambda r: (CONDITIONS_ORDER.index(r["condition_id"]), MODELS_ORDER.index(r["model"]))))}
        </div>
        </details>
    </section>
    """


def render_page():
    # Overall data for charts
    by_cond_all = summarize_by_condition()
    labels = [COND_LABELS[c] for c in CONDITIONS_ORDER if c in by_cond_all]
    kept_conds = [c for c in CONDITIONS_ORDER if c in by_cond_all]

    # tokens by condition per model
    token_data = {}
    for m in MODELS_ORDER:
        by_cond_m = summarize_by_condition(model_filter=m)
        token_data[MODEL_LABELS[m]] = [by_cond_m.get(c, {"avg_total": 0})["avg_total"] for c in kept_conds]
    token_colors = {MODEL_LABELS[m]: MODEL_COLORS[m] for m in MODELS_ORDER}

    # success rate by condition per model (percent)
    success_data = {}
    for m in MODELS_ORDER:
        by_cond_m = summarize_by_condition(model_filter=m)
        vals = []
        for c in kept_conds:
            s = by_cond_m.get(c)
            if not s or s["runs"] == 0:
                vals.append(0)
                continue
            score = (s["success"] * 1.0 + s["partial"] * 0.5) / s["runs"] * 100
            vals.append(round(score))
        success_data[MODEL_LABELS[m]] = vals

    # Summary numbers
    total_runs = len(RESULTS)
    good_runs = sum(1 for r in RESULTS if r["status"] == "ok")
    successes = sum(1 for r in RESULTS if r["verdict"] == "success")
    partials = sum(1 for r in RESULTS if r["verdict"] == "partial")
    fails = sum(1 for r in RESULTS if r["verdict"] == "fail")

    style = """
    body { background: #0b0f19; color: #e5e7eb; font: 14px/1.55 -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; padding: 0; }
    main { max-width: 1200px; margin: 0 auto; padding: 32px 24px 64px; }
    h1 { font-size: 28px; margin: 0 0 4px; color: #f9fafb; }
    h2 { font-size: 20px; margin: 40px 0 12px; color: #f3f4f6; padding-top: 12px; border-top: 1px solid #1f2937; }
    h3 { font-size: 17px; margin: 24px 0 8px; color: #e5e7eb; }
    h4 { font-size: 14px; margin: 16px 0 6px; color: #cbd5e1; }
    h5 { font-size: 12px; margin: 10px 0 4px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; }
    p { color: #cbd5e1; }
    a { color: #93c5fd; }
    code { background: #111827; padding: 1px 5px; border-radius: 3px; font-size: 12px; }
    .subtitle { color: #94a3b8; margin: 0 0 8px; }
    .stats { display: flex; gap: 16px; margin: 20px 0 32px; flex-wrap: wrap; }
    .stat { background: #111827; border: 1px solid #1f2937; padding: 12px 16px; border-radius: 6px; min-width: 130px; }
    .stat-label { color: #9ca3af; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }
    .stat-value { font-size: 24px; color: #f3f4f6; font-weight: 600; margin-top: 4px; }
    .charts { display: grid; grid-template-columns: 1fr; gap: 24px; margin: 24px 0; }
    @media (min-width: 800px) { .charts { grid-template-columns: 1fr 1fr; } }
    .chart-container { background: #111827; border: 1px solid #1f2937; border-radius: 6px; padding: 12px; overflow-x: auto; }
    .chart { display: block; max-width: 100%; height: auto; min-width: 500px; }
    table.matrix { border-collapse: collapse; width: 100%; margin: 8px 0 16px; font-size: 13px; }
    table.matrix th, table.matrix td { padding: 8px 10px; border: 1px solid #1f2937; text-align: left; }
    table.matrix th { background: #0f172a; color: #cbd5e1; font-weight: 500; }
    table.matrix td.cell { text-align: center; vertical-align: middle; }
    table.matrix td.na { color: #4b5563; text-align: center; font-style: italic; }
    table.matrix td.v-success { background: rgba(74,222,128,0.08); }
    table.matrix td.v-partial { background: rgba(251,191,36,0.08); }
    table.matrix td.v-fail { background: rgba(248,113,113,0.08); }
    .v-pill { display: inline-block; width: 18px; height: 18px; border-radius: 3px; text-align: center; line-height: 18px; font-weight: 700; font-size: 10px; margin-right: 6px; }
    td.v-success .v-pill { background: #4ade80; color: #052e16; }
    td.v-partial .v-pill { background: #fbbf24; color: #451a03; }
    td.v-fail .v-pill { background: #f87171; color: #450a0a; }
    .tok { color: #94a3b8; font-size: 12px; }
    .task-section { background: #0d1220; border: 1px solid #1f2937; border-radius: 8px; padding: 16px 20px; margin: 16px 0; }
    .run-detail { margin: 4px 0; background: #0f172a; border: 1px solid #1e293b; border-radius: 4px; padding: 4px 10px; }
    .run-detail summary { cursor: pointer; padding: 6px 4px; display: flex; flex-wrap: wrap; align-items: center; gap: 10px; font-size: 13px; }
    .run-detail summary::marker { color: #64748b; }
    .model-chip { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: 500; }
    .model-chip.opus { background: #4c1d95; color: #ddd6fe; }
    .model-chip.sonnet { background: #075985; color: #bae6fd; }
    .model-chip.fable { background: #831843; color: #fbcfe8; }
    .model-chip.copilot { background: #064e3b; color: #a7f3d0; }
    .cond { color: #cbd5e1; }
    .verdict { padding: 2px 6px; border-radius: 3px; font-size: 10px; font-weight: 700; letter-spacing: 0.4px; }
    .verdict-success { background: #4ade80; color: #052e16; }
    .verdict-partial { background: #fbbf24; color: #451a03; }
    .verdict-fail { background: #f87171; color: #450a0a; }
    .tokens { color: #94a3b8; font-size: 12px; margin-left: auto; }
    .run-inner { padding: 10px 4px 16px; }
    .run-meta { color: #94a3b8; font-size: 12px; display: flex; gap: 20px; margin: 4px 0 12px; flex-wrap: wrap; }
    .run-meta .rat { color: #cbd5e1; font-style: italic; margin-left: auto; }
    pre.prompt, pre.response { background: #050914; border: 1px solid #1e293b; border-radius: 4px; padding: 10px 12px; overflow-x: auto; font-size: 12px; color: #cbd5e1; white-space: pre-wrap; word-wrap: break-word; max-height: 460px; overflow-y: auto; }
    pre.prompt { border-left: 3px solid #38bdf8; }
    pre.response { border-left: 3px solid #a78bfa; }
    .all-runs summary { padding: 8px 4px; cursor: pointer; color: #94a3b8; font-size: 12px; }
    section.method p, section.method li { color: #cbd5e1; }
    section.method ul { padding-left: 20px; }
    section.repro p, section.repro li { color: #cbd5e1; }
    .repro-item { margin: 4px 0; background: #0f172a; border: 1px solid #1e293b; border-radius: 4px; padding: 4px 10px; }
    .repro-item summary { cursor: pointer; padding: 6px 4px; font-size: 13px; color: #e5e7eb; }
    .repro-item pre { max-height: 340px; }
    footer { color: #6b7280; font-size: 11px; margin-top: 40px; text-align: center; }
    """

    method_html = """
    <section class="method">
        <h2>Methodology</h2>
        <p>6 text tasks by 7 prompt conditions by 4 models: Opus 4.7, Sonnet 4.5, Fable 5.1, and GitHub Copilot CLI on gpt-5.4. The rtk condition only applies to the two tasks where the model would invoke CLI tools, so it is marked n/a on the other four. Net: 38 runs per model, 152 runs total.</p>
        <h3>Execution</h3>
        <ul>
            <li>Each Claude run (Opus, Sonnet, Fable) ran in an isolated Claude Code sub-agent with a <code>model</code> override. The sub-agent read one prompt file, produced its answer, wrote the answer to a JSON file, and returned <code>DONE</code>.</li>
            <li>Each Copilot run invoked the GitHub Copilot CLI (v1.0.82) with <code>copilot --yolo -p &lt;prompt&gt; --model gpt-5.4</code>. Copilot's trailing session-summary footer (Changes, Requests, Tokens, Resume lines) was stripped before saving the response.</li>
            <li>Sub-agents and Copilot runs both start in fresh contexts, so runs do not carry state between them. Both harnesses add roughly constant system-prompt overhead per call that is not attributed to the task.</li>
        </ul>
        <h3>Token measurement</h3>
        <ul>
            <li>Reported tokens use the <code>chars &divide; 4</code> estimate applied to the exact prompt text sent to the model and the exact response received. The estimate is consistent across runs, so relative comparisons hold.</li>
            <li>This represents the tokens you would pay for if you sent only the task prompt through the API. It does not include the sub-agent's fixed system-prompt overhead, which is roughly constant across conditions.</li>
        </ul>
        <h3>Conditions</h3>
        <ul>
            <li><strong>Baseline.</strong> Simple, brief task instruction with no shaping.</li>
            <li><strong>Detailed instructions.</strong> One prescriptive paragraph telling the model exactly how to approach and format the task.</li>
            <li><strong>Caveman-speak.</strong> Tell the model to drop stopwords and grammatical filler, and to think in the same style. Inspired by juliusbrussee/caveman.</li>
            <li><strong>HTML output.</strong> Baseline plus a request for a full standalone HTML document as the answer.</li>
            <li><strong>rtk (CLI compression).</strong> For tasks where the model uses CLI tools to gather signal, wrap those commands with the <code>rtk</code> proxy (github.com/rtk-ai/rtk) so their stdout is filtered before it reaches the model context. Uses <code>rtk read</code>, <code>rtk err</code>, and <code>rtk grep</code>. Applied to tasks 1 (bug find) and 2 (unit tests). Marked <em>n/a</em> for tasks that do not call CLI tools.</li>
            <li><strong>Hard output cap.</strong> Prepend an instruction to skip preamble, disclaimers, and closings, with a hard cap of 150 output tokens.</li>
            <li><strong>SPR-compressed input.</strong> Preprocess the prompt to drop stopwords and collapse whitespace, in the style of Sparse Priming Representations. Reduces input size at the cost of some grammar the model has to reconstruct.</li>
        </ul>
        <h3>Tasks</h3>
        <ul>
            <li><strong>T1. Find bugs in code.</strong> Medium Python snippet with 3 subtle bugs.</li>
            <li><strong>T2. Unit tests to &gt;90% coverage.</strong> A LateFeeCalculator class with 8 branch behaviors.</li>
            <li><strong>T3. Summarize legal snippet.</strong> Indemnification and limit-of-liability clause. 15 items scored.</li>
            <li><strong>T4. Summarize meeting transcript.</strong> Q3 planning meeting. 7 key points and 7 next-step actions scored.</li>
            <li><strong>T5. Extract resume to JSON.</strong> Structured extraction against a target schema.</li>
            <li><strong>T6. Multi-step arithmetic.</strong> Chained calculations with an irrelevant number included to test whether the model excludes it.</li>
        </ul>
        <h3>Scoring</h3>
        <ul>
            <li>Each task has a rubric. Verdicts: <span class="verdict verdict-success">SUCCESS</span> if the task is fully solved, <span class="verdict verdict-partial">PARTIAL</span> if most of the rubric is covered, <span class="verdict verdict-fail">FAIL</span> if key items are missing or the answer is wrong.</li>
            <li>Scoring is automated (keyword and JSON checks) so results are reproducible. Automated scoring can under-credit an answer that uses synonyms not in the keyword list. That bias applies the same way to every condition and model, so relative comparisons hold. Absolute success rates are conservative.</li>
        </ul>
    </section>
    """

    body = f"""
    <main>
        <h1>Token-usage vs task-success experiment</h1>
        <p class="subtitle">Comparing 3 Claude models × 7 prompt conditions × 6 tasks (114 runs).</p>

        <div class="stats">
            <div class="stat"><div class="stat-label">Total runs</div><div class="stat-value">{total_runs}</div></div>
            <div class="stat"><div class="stat-label">Successful</div><div class="stat-value">{successes}</div></div>
            <div class="stat"><div class="stat-label">Partial</div><div class="stat-value">{partials}</div></div>
            <div class="stat"><div class="stat-label">Failed</div><div class="stat-value">{fails}</div></div>
            <div class="stat"><div class="stat-label">Output missing</div><div class="stat-value">{total_runs - good_runs}</div></div>
        </div>

        <h2>Overview</h2>
        {render_condition_summary()}
        <div class="charts">
            <div class="chart-container">{bar_chart_grouped(token_data, labels, list(token_data.keys()), "Avg total tokens (prompt + response) per run, by condition", "tokens", token_colors, height=320)}</div>
            <div class="chart-container">{bar_chart_grouped(success_data, labels, list(success_data.keys()), "Task-success score (success=100, partial=50), by condition", "score", token_colors, height=320, max_y=100)}</div>
        </div>

        {method_html}

        <h2>Per-task results</h2>
        {"".join(render_task_section(t) for t in TASKS_ORDER)}

        {render_reproduction()}

        <footer>Generated by the token-usage experiment harness. Sub-agents run in isolation; automated scoring; char-based token estimation.</footer>
    </main>
    """

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Token-usage experiment report</title>
<style>{style}</style>
</head>
<body data-theme="dark">
{body}
</body>
</html>"""


if __name__ == "__main__":
    out = ROOT / "report.html"
    out.write_text(render_page())
    print(f"Wrote {out} ({out.stat().st_size:,} bytes)")
