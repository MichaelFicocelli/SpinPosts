# Codex runbook: token-usage experiment

Self-contained playbook for reproducing a token-usage vs task-success experiment against OpenAI Codex. Every input, prompt, and scoring rubric is inlined below so this single markdown file is all you need.

## What you're producing

For each of the 38 (task, condition) combinations listed, capture:

1. The model's full response text.
2. Token counts if Codex exposes them: input tokens, output tokens, and reasoning tokens if any.
3. Wall-clock duration of the call.

Save each response as `outputs/codex/<run_id>.json` in the shape:

```json
{"response": "<full response text>", "tokens": {"input": 0, "output": 0, "reasoning": 0}, "duration_ms": 0}
```

Return the whole `outputs/codex/` directory. Scoring is automated on our side against the same rubrics in this document.

## Getting Codex ready

Install and authenticate the OpenAI Codex CLI per its docs (https://github.com/openai/codex). Verify:

```
codex --version
codex --help | grep -E '(prompt|model|json)'
```

Then confirm a non-interactive call works. The exact flag names may differ across Codex versions; the common shapes are:

```
# Newer builds
codex exec --model gpt-5.4 "Say only the word: pong"

# Older builds
codex --prompt "Say only the word: pong" --model gpt-5.4
```

pick one model (e.g. `gpt-5.4`) and use it for all 38 runs so the comparison is clean. Then repeat with a second model for comparison.

## Runner script (Python)

Adjust `CODEX_CMD` to your Codex CLI's actual invocation. Everything else can stay as-is. The script reads the prompts inline from this file (search for a fenced `text` block whose caption matches `PROMPT: <run_id>`) or you can paste the prompts into `prompts/<run_id>.txt` first.

```python
import json, re, subprocess, time
from pathlib import Path

PROMPTS = Path('prompts')  # directory with one <run_id>.txt per run
OUT = Path('outputs/codex')
OUT.mkdir(parents=True, exist_ok=True)

# Adjust to whatever your Codex build wants. --yolo-equivalent flag if needed.
def codex_call(prompt: str) -> dict:
    t0 = time.time()
    r = subprocess.run(
        ['codex', 'exec', '--model', 'gpt-5.4', prompt],
        capture_output=True, text=True, timeout=300,
    )
    dur = int((time.time() - t0) * 1000)
    # Strip any trailing session-summary footer your build emits.
    lines = (r.stdout or '').splitlines()
    keep, footer_re = [], re.compile(r'^(Changes|Requests|Tokens|Session|Model)\\s')
    for ln in lines:
        if footer_re.match(ln): break
        keep.append(ln)
    while keep and not keep[-1].strip(): keep.pop()
    return {'response': '\n'.join(keep), 'duration_ms': dur,
            'tokens': {'input': 0, 'output': 0, 'reasoning': 0}}

for pf in sorted(PROMPTS.glob('*.txt')):
    run_id = pf.stem
    out_path = OUT / f'{run_id}.json'
    if out_path.exists() and out_path.stat().st_size > 40:
        print(f'skip {run_id}'); continue
    print(f'run  {run_id}')
    data = codex_call(pf.read_text())
    out_path.write_text(json.dumps(data, indent=2))
```

If Codex prints token counts to stdout in a machine-readable form, parse them and fill in the `tokens` dict. Otherwise leave zeros: we can char-estimate on our side.

## Task inputs

The six input specimens each prompt is built from. Included for reference only; the prompts below already have them interpolated.

### t1_bugs: Find bugs in code

Identify and fix bugs in a Python snippet.

<details><summary>Show input file (<code>task1_buggy_code.py</code>)</summary>

```python
from collections import defaultdict


def group_transactions(transactions):
    """Group transactions by account_id and compute the running balance
    after each transaction, sorted by timestamp (oldest first).

    A transaction is a dict: {"account_id": str, "amount": float,
    "timestamp": int, "kind": "credit" | "debit"}.
    """
    grouped = defaultdict(list)
    for tx in transactions:
        grouped[tx["account_id"]].append(tx)

    result = {}
    for account_id, txs in grouped.items():
        txs.sort(key=lambda t: t["timestamp"], reverse=True)
        balance = 0
        history = []
        for tx in txs:
            if tx["kind"] == "credit":
                balance += tx["amount"]
            else:
                balance -= tx["amount"]
            history.append({"tx": tx, "balance_after": balance})
        result[account_id] = history

    return result


def average_daily_balance(history, start_day, end_day):
    """Given a per-account history (list from group_transactions),
    return the average balance across the [start_day, end_day) window.
    Timestamps in history are epoch seconds.
    """
    day_seconds = 86400
    if not history:
        return 0

    balances_by_day = {}
    for entry in history:
        day = entry["tx"]["timestamp"] // day_seconds
        balances_by_day[day] = entry["balance_after"]

    total = 0
    for day in range(start_day, end_day):
        total += balances_by_day.get(day, 0)
    return total / (end_day - start_day)


def top_accounts_by_activity(transactions, top_n=5):
    """Return the top-N account_ids by number of transactions."""
    counts = defaultdict(int)
    for tx in transactions:
        counts[tx["account_id"]] += 1
    return sorted(counts.items(), key=lambda kv: kv[1])[:top_n]

```

</details>

### t2_tests: Unit tests to >90% coverage

Write pytest tests for a Python class covering documented behaviors.

<details><summary>Show input file (<code>task2_code_for_tests.py</code>)</summary>

```python
from datetime import date, timedelta


class LateFeeCalculator:
    """Calculates late fees on invoices for a court finance system.

    Rules:
      - Grace period: 10 days after due_date, no fee.
      - After grace period: 1.5% of outstanding balance per 30-day period,
        prorated by day (i.e. per-day rate = 1.5% / 30).
      - Minimum fee once past grace: $5.
      - Maximum fee: 25% of the original balance (hard cap).
      - Weekends do not count toward the days-late tally (Mon-Fri only).
      - Fees are computed in whole cents (round half up).
      - If balance <= 0, fee is 0 regardless of dates.
    """

    GRACE_DAYS = 10
    MONTHLY_RATE = 0.015
    MIN_FEE_CENTS = 500
    MAX_FEE_FRACTION = 0.25

    def __init__(self, today=None):
        self._today = today or date.today()

    def _weekday_days_between(self, start, end):
        if end <= start:
            return 0
        days = 0
        current = start
        while current < end:
            if current.weekday() < 5:
                days += 1
            current += timedelta(days=1)
        return days

    def compute_fee_cents(self, balance_cents, due_date):
        if balance_cents <= 0:
            return 0
        days_past_due = self._weekday_days_between(due_date, self._today)
        billable_days = days_past_due - self.GRACE_DAYS
        if billable_days <= 0:
            return 0
        per_day_rate = self.MONTHLY_RATE / 30
        raw_fee = balance_cents * per_day_rate * billable_days
        rounded = int(raw_fee + 0.5)
        capped = min(rounded, int(balance_cents * self.MAX_FEE_FRACTION))
        return max(capped, self.MIN_FEE_CENTS)

```

</details>

### t3_legal: Summarize legal snippet

Explain a contract section in plain language and define key legal terms.

<details><summary>Show input file (<code>task3_legal_snippet.md</code>)</summary>

```text
# Section 7 — Indemnification and Limitation of Liability

7.1 **Mutual Indemnification.** Each Party (the "Indemnifying Party") shall
defend, indemnify, and hold harmless the other Party and its officers,
directors, employees, and agents (the "Indemnified Parties") from and against
any and all third-party claims, demands, actions, suits, or proceedings
(collectively, "Claims") and all resulting losses, damages, liabilities,
settlements, judgments, fines, penalties, costs, and expenses (including
reasonable outside counsel fees) (collectively, "Losses"), to the extent such
Claims arise out of or relate to (a) the Indemnifying Party's breach of any
representation, warranty, or covenant hereunder; (b) the Indemnifying Party's
gross negligence or willful misconduct; or (c) any allegation that the
Indemnifying Party's Deliverables, when used in accordance with this Agreement,
infringe or misappropriate any third party's intellectual property rights,
provided that the foregoing (c) shall not apply to the extent a Claim arises
from (i) modifications made by the Indemnified Parties, (ii) combination of the
Deliverables with materials not supplied by the Indemnifying Party where the
infringement would not have occurred but for such combination, or (iii) use of
the Deliverables outside the scope expressly permitted under this Agreement.

7.2 **Indemnification Procedure.** The Indemnified Parties shall (a) promptly
notify the Indemnifying Party in writing of any Claim (provided that failure to
so notify shall not relieve the Indemnifying Party of its obligations except to
the extent it is materially prejudiced thereby), (b) tender sole control of the
defense and settlement of the Claim to the Indemnifying Party (provided that
the Indemnifying Party shall not settle any Claim that admits liability of, or
imposes any non-monetary obligation on, the Indemnified Parties without their
prior written consent, not to be unreasonably withheld), and (c) provide
reasonable cooperation at the Indemnifying Party's expense.

7.3 **Limitation of Liability.** EXCEPT FOR (i) A PARTY'S INDEMNIFICATION
OBLIGATIONS UNDER SECTION 7.1, (ii) BREACHES OF CONFIDENTIALITY UNDER SECTION
9, (iii) A PARTY'S GROSS NEGLIGENCE OR WILLFUL MISCONDUCT, OR (iv) A PARTY'S
INFRINGEMENT OF THE OTHER PARTY'S INTELLECTUAL PROPERTY RIGHTS, IN NO EVENT
SHALL EITHER PARTY BE LIABLE TO THE OTHER FOR ANY INDIRECT, INCIDENTAL,
CONSEQUENTIAL, SPECIAL, PUNITIVE, OR EXEMPLARY DAMAGES, OR FOR ANY LOST
PROFITS, LOST REVENUE, LOSS OF GOODWILL, OR LOSS OF DATA, HOWEVER CAUSED AND
UNDER ANY THEORY OF LIABILITY, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
DAMAGES. SUBJECT TO THE FOREGOING, EACH PARTY'S TOTAL CUMULATIVE LIABILITY
ARISING OUT OF OR RELATING TO THIS AGREEMENT SHALL NOT EXCEED THE GREATER OF
(A) THE FEES PAID OR PAYABLE BY CUSTOMER TO PROVIDER UNDER THIS AGREEMENT IN
THE TWELVE (12) MONTHS PRECEDING THE FIRST EVENT GIVING RISE TO LIABILITY, OR
(B) ONE HUNDRED THOUSAND U.S. DOLLARS ($100,000).

```

</details>

### t4_meeting: Summarize meeting transcript

Bullet the key decisions and action items from a meeting.

<details><summary>Show input file (<code>task4_meeting_transcript.md</code>)</summary>

```text
# Q3 Planning — Product / Engineering / Ops sync — 2026-08-27

**Attendees:** Priya (PM), Marcus (Eng lead), Jenna (Ops), Dan (Design), Sara (VP Product)

---

**Priya:** Thanks all for joining. Big agenda — we need to lock Q3 scope by Friday, then Sara can take it to the exec review Monday. Three headliners on the table: the reconciliation revamp, the mobile receipt-capture feature, and the vendor payout SLA push. Let's start with reconciliation.

**Marcus:** So on reconciliation — the current engine chokes on multi-currency batches. We've had three incidents this quarter and support ticket volume for reconciliation issues is up 40% quarter over quarter. My team scoped a rewrite that's roughly six engineer-weeks. That includes migrating the FX rounding module. We'd need Karim from platform for two of those weeks to help with the ledger integration.

**Sara:** Six engineer-weeks is a lot. What's the buy-vs-build here? Is there a vendor?

**Marcus:** We looked at two — Recur and LedgerFlow. Recur is $180K/year for our volume, LedgerFlow is $140K but doesn't handle our jurisdiction-specific tax codes. Both would still need integration work, probably three engineer-weeks. Not a great deal.

**Sara:** Okay, build wins. Priya, put reconciliation as the Q3 anchor. Marcus, sync with Karim's manager this week and confirm his availability.

**Priya:** Noted. Mobile receipt-capture next. Dan, where are we on design?

**Dan:** Flows are done, prototype tested with six users. Two big things came out of testing: users want to bulk-select receipts before uploading, and the OCR confidence indicator needs to be way more prominent. Bulk-select is not currently in scope; that would add maybe a sprint of work.

**Marcus:** If bulk-select is a sprint I'd want to descope something else. We're already stretched with reconciliation.

**Sara:** Let's ship v1 without bulk-select. Add a note to the roadmap for a fast-follow. Dan, please update the specs.

**Dan:** Will do by Wednesday.

**Priya:** Vendor payout SLA — Jenna, this one's yours.

**Jenna:** Right. The finance team wants us to guarantee payouts within 48 hours from invoice approval. Current p95 is 71 hours. Two bottlenecks: manual approval routing (that's ops), and the batching window on the ACH send job (that's eng). If eng cuts the batching window from 12 hours to 4, and ops adds a second approver on the west-coast shift, we can hit 48h p95 by mid-Q3.

**Marcus:** Cutting the ACH batch window means more ACH files per day, more monitoring overhead. Doable but not free — half a sprint of eng time plus SRE sign-off.

**Sara:** Do the trade-off analysis and bring it back next week. If SRE says the monitoring load is manageable, we do it. Otherwise we look at intermediate targets.

**Priya:** Two smaller things — the audit-log retention update is being pushed to Q4, that's confirmed with Legal. And the internal admin-tool refresh is still owned by the intern crew, no changes there.

**Sara:** One last thing. HR flagged that we've had a spike in bug-bash burnout on the engineering side. Marcus, can you propose a rotating on-call structure by end of month? Doesn't need to be big, just a proposal.

**Marcus:** Yep, I'll have something by the 31st.

**Priya:** Okay. Recap next steps then. Marcus: confirm Karim, propose on-call rotation by 31st, do ACH trade-off analysis. Dan: update mobile specs by Wednesday. Jenna: pair with Marcus on the ACH analysis. Sara: exec review Monday. I'll circulate the scope draft Thursday morning for review before Friday lock.

**Sara:** Good. Thanks everyone.

```

</details>

### t5_extract: Extract resume to JSON

Extract structured fields from a resume into a target JSON schema.

<details><summary>Show input file (<code>task5_resume_snippet.md</code>)</summary>

```text
# Alex Chen — Senior Software Engineer

alex.chen@example.com · (415) 555-0134 · San Francisco, CA · github.com/alexc

Software engineer with 9 years of experience shipping backend services and
data pipelines at fintech and healthtech companies. Comfortable across the
stack; strongest in distributed systems and API design.

## Experience

**Staff Software Engineer** — Northwind Health, Remote — Mar 2023 to present
- Led migration of billing service from Ruby monolith to Go microservices,
  cutting p99 latency from 1.8s to 340ms.
- Owner of the claims-ingestion pipeline (Kafka + Flink), 2M events/day.
- Mentored 3 engineers, ran the weekly design-review meeting.

**Senior Software Engineer** — Cascade Payments, San Francisco — Aug 2019 to Feb 2023
- Built the merchant-onboarding API in Node.js/TypeScript; grew from 200 to
  40,000 merchants over three years.
- Introduced feature-flag rollout process, adopted org-wide within 6 months.
- On-call rotation for payments platform, ~1 primary week per month.

**Software Engineer** — Acme Corp, San Francisco — Jul 2017 to Jul 2019
- Wrote the internal reporting service (Python/Django, Postgres). Retired 2021.

## Skills

Go, Python, TypeScript, Node.js, Kafka, Flink, Postgres, Redis, Kubernetes,
Terraform, AWS (EKS, RDS, Lambda), gRPC, REST, distributed tracing, on-call.

## Education

B.S. Computer Science, UC Berkeley — 2017

```

</details>

### t6_math: Multi-step arithmetic

Solve a multi-step word problem with a distractor number.

<details><summary>Show input file (<code>task6_word_problem.md</code>)</summary>

```text
# Multi-step reasoning problem

A regional courthouse processes filing fees for three case types. In the month
of March, the courthouse processed:

- 420 civil filings at a base fee of $85 each.
- 175 family-law filings at a base fee of $120 each.
- 60 probate filings at a base fee of $210 each.

Rules:
- A 6% state surcharge is added to every filing fee.
- Filers who submit electronically get a $5 credit per filing (deducted from
  what they owe). 70% of civil filings, 40% of family-law filings, and 25% of
  probate filings were submitted electronically.
- The courthouse retains 82% of the collected total; the remaining 18% is
  remitted to the state.
- Note: the courthouse also runs a passport-services desk that took in $9,400
  in March, but that revenue is handled separately and is NOT part of filing
  fee collections.

Question: How much did the courthouse RETAIN from filing fees collected in
March? Round to the nearest dollar.

```

</details>

## Conditions

Each of the 38 runs is a (task, condition) pair. The condition changes how the prompt is built from the task input.

- **c1_baseline — Baseline.** Simple, brief task instruction. No shaping.
- **c2_detailed — Detailed instructions.** One prescriptive paragraph telling the model exactly how to approach and format the task.
- **c3_caveman — Caveman-speak.** Model is told to drop stopwords and grammatical filler and think in the same style.
- **c4_html — HTML output.** Baseline plus a request for a full standalone HTML document as the answer.
- **c5_rtk — rtk (CLI compression).** For tasks that use CLI tools, wrap commands with the rtk CLI proxy so command output is filtered before it reaches the model context. Applied only to T1 and T2.
- **c6_hardcap — Hard output cap.** Prepend an instruction to skip preamble and closings, with a hard cap of 150 output tokens.
- **c7_spr — SPR-compressed input.** Preprocess the prompt to drop stopwords and collapse whitespace, in the style of Sparse Priming Representations.

## The 38 prompts

Each block below is the exact text to send as the user message. The heading gives the `run_id` and the filename `prompts/<run_id>.txt` matches the runner script above.

### PROMPT: t1_bugs__c1_baseline

``````text
The following Python code has one or more subtle bugs. Identify the bug(s) and propose a specific fix for each. Code:

from collections import defaultdict


def group_transactions(transactions):
    """Group transactions by account_id and compute the running balance
    after each transaction, sorted by timestamp (oldest first).

    A transaction is a dict: {"account_id": str, "amount": float,
    "timestamp": int, "kind": "credit" | "debit"}.
    """
    grouped = defaultdict(list)
    for tx in transactions:
        grouped[tx["account_id"]].append(tx)

    result = {}
    for account_id, txs in grouped.items():
        txs.sort(key=lambda t: t["timestamp"], reverse=True)
        balance = 0
        history = []
        for tx in txs:
            if tx["kind"] == "credit":
                balance += tx["amount"]
            else:
                balance -= tx["amount"]
            history.append({"tx": tx, "balance_after": balance})
        result[account_id] = history

    return result


def average_daily_balance(history, start_day, end_day):
    """Given a per-account history (list from group_transactions),
    return the average balance across the [start_day, end_day) window.
    Timestamps in history are epoch seconds.
    """
    day_seconds = 86400
    if not history:
        return 0

    balances_by_day = {}
    for entry in history:
        day = entry["tx"]["timestamp"] // day_seconds
        balances_by_day[day] = entry["balance_after"]

    total = 0
    for day in range(start_day, end_day):
        total += balances_by_day.get(day, 0)
    return total / (end_day - start_day)


def top_accounts_by_activity(transactions, top_n=5):
    """Return the top-N account_ids by number of transactions."""
    counts = defaultdict(int)
    for tx in transactions:
        counts[tx["account_id"]] += 1
    return sorted(counts.items(), key=lambda kv: kv[1])[:top_n]

``````

### PROMPT: t1_bugs__c2_detailed

``````text
You are reviewing Python code for correctness. Read every function carefully. For EACH bug: (1) name the function it lives in, (2) quote the exact line or expression that is wrong, (3) explain why it is wrong in one sentence, and (4) show the specific code change that fixes it. Check for off-by-one errors, wrong sort order, missing edge cases, and any place a docstring or function name contradicts what the code actually does. Do not invent bugs that are not real. Code:

from collections import defaultdict


def group_transactions(transactions):
    """Group transactions by account_id and compute the running balance
    after each transaction, sorted by timestamp (oldest first).

    A transaction is a dict: {"account_id": str, "amount": float,
    "timestamp": int, "kind": "credit" | "debit"}.
    """
    grouped = defaultdict(list)
    for tx in transactions:
        grouped[tx["account_id"]].append(tx)

    result = {}
    for account_id, txs in grouped.items():
        txs.sort(key=lambda t: t["timestamp"], reverse=True)
        balance = 0
        history = []
        for tx in txs:
            if tx["kind"] == "credit":
                balance += tx["amount"]
            else:
                balance -= tx["amount"]
            history.append({"tx": tx, "balance_after": balance})
        result[account_id] = history

    return result


def average_daily_balance(history, start_day, end_day):
    """Given a per-account history (list from group_transactions),
    return the average balance across the [start_day, end_day) window.
    Timestamps in history are epoch seconds.
    """
    day_seconds = 86400
    if not history:
        return 0

    balances_by_day = {}
    for entry in history:
        day = entry["tx"]["timestamp"] // day_seconds
        balances_by_day[day] = entry["balance_after"]

    total = 0
    for day in range(start_day, end_day):
        total += balances_by_day.get(day, 0)
    return total / (end_day - start_day)


def top_accounts_by_activity(transactions, top_n=5):
    """Return the top-N account_ids by number of transactions."""
    counts = defaultdict(int)
    for tx in transactions:
        counts[tx["account_id"]] += 1
    return sorted(counts.items(), key=lambda kv: kv[1])[:top_n]

``````

### PROMPT: t1_bugs__c3_caveman

``````text
CAVEMAN MODE. Talk caveman. Drop 'the', 'a', 'is', 'are', 'that', 'to', 'of' when meaning still clear. Short words. Grunt-style. THINK in caveman too, not just output. Save word. Save token. Still solve task correctly.

TASK:
The following Python code has one or more subtle bugs. Identify the bug(s) and propose a specific fix for each. Code:

from collections import defaultdict


def group_transactions(transactions):
    """Group transactions by account_id and compute the running balance
    after each transaction, sorted by timestamp (oldest first).

    A transaction is a dict: {"account_id": str, "amount": float,
    "timestamp": int, "kind": "credit" | "debit"}.
    """
    grouped = defaultdict(list)
    for tx in transactions:
        grouped[tx["account_id"]].append(tx)

    result = {}
    for account_id, txs in grouped.items():
        txs.sort(key=lambda t: t["timestamp"], reverse=True)
        balance = 0
        history = []
        for tx in txs:
            if tx["kind"] == "credit":
                balance += tx["amount"]
            else:
                balance -= tx["amount"]
            history.append({"tx": tx, "balance_after": balance})
        result[account_id] = history

    return result


def average_daily_balance(history, start_day, end_day):
    """Given a per-account history (list from group_transactions),
    return the average balance across the [start_day, end_day) window.
    Timestamps in history are epoch seconds.
    """
    day_seconds = 86400
    if not history:
        return 0

    balances_by_day = {}
    for entry in history:
        day = entry["tx"]["timestamp"] // day_seconds
        balances_by_day[day] = entry["balance_after"]

    total = 0
    for day in range(start_day, end_day):
        total += balances_by_day.get(day, 0)
    return total / (end_day - start_day)


def top_accounts_by_activity(transactions, top_n=5):
    """Return the top-N account_ids by number of transactions."""
    counts = defaultdict(int)
    for tx in transactions:
        counts[tx["account_id"]] += 1
    return sorted(counts.items(), key=lambda kv: kv[1])[:top_n]

``````

### PROMPT: t1_bugs__c4_html

``````text
The following Python code has one or more subtle bugs. Identify the bug(s) and propose a specific fix for each. Code:

from collections import defaultdict


def group_transactions(transactions):
    """Group transactions by account_id and compute the running balance
    after each transaction, sorted by timestamp (oldest first).

    A transaction is a dict: {"account_id": str, "amount": float,
    "timestamp": int, "kind": "credit" | "debit"}.
    """
    grouped = defaultdict(list)
    for tx in transactions:
        grouped[tx["account_id"]].append(tx)

    result = {}
    for account_id, txs in grouped.items():
        txs.sort(key=lambda t: t["timestamp"], reverse=True)
        balance = 0
        history = []
        for tx in txs:
            if tx["kind"] == "credit":
                balance += tx["amount"]
            else:
                balance -= tx["amount"]
            history.append({"tx": tx, "balance_after": balance})
        result[account_id] = history

    return result


def average_daily_balance(history, start_day, end_day):
    """Given a per-account history (list from group_transactions),
    return the average balance across the [start_day, end_day) window.
    Timestamps in history are epoch seconds.
    """
    day_seconds = 86400
    if not history:
        return 0

    balances_by_day = {}
    for entry in history:
        day = entry["tx"]["timestamp"] // day_seconds
        balances_by_day[day] = entry["balance_after"]

    total = 0
    for day in range(start_day, end_day):
        total += balances_by_day.get(day, 0)
    return total / (end_day - start_day)


def top_accounts_by_activity(transactions, top_n=5):
    """Return the top-N account_ids by number of transactions."""
    counts = defaultdict(int)
    for tx in transactions:
        counts[tx["account_id"]] += 1
    return sorted(counts.items(), key=lambda kv: kv[1])[:top_n]


Respond with a complete standalone HTML document (with <!doctype html>, <head>, <style>, <body>) that presents the task and your answer clearly.
``````

### PROMPT: t1_bugs__c5_rtk

``````text
You have access to Bash and the `rtk` CLI (github.com/rtk-ai/rtk). Save the code below to $TMPDIR/target.py. Use rtk-wrapped commands wherever you would otherwise use raw shell output as evidence:
  * `rtk read -l aggressive $TMPDIR/target.py` to look at the code again if needed.
  * `rtk err python3 -m py_compile $TMPDIR/target.py` for syntax checks.
  * `rtk grep <pattern> $TMPDIR/target.py` to locate constructs.
Then identify the bug(s) and propose specific fixes.

Code:

from collections import defaultdict


def group_transactions(transactions):
    """Group transactions by account_id and compute the running balance
    after each transaction, sorted by timestamp (oldest first).

    A transaction is a dict: {"account_id": str, "amount": float,
    "timestamp": int, "kind": "credit" | "debit"}.
    """
    grouped = defaultdict(list)
    for tx in transactions:
        grouped[tx["account_id"]].append(tx)

    result = {}
    for account_id, txs in grouped.items():
        txs.sort(key=lambda t: t["timestamp"], reverse=True)
        balance = 0
        history = []
        for tx in txs:
            if tx["kind"] == "credit":
                balance += tx["amount"]
            else:
                balance -= tx["amount"]
            history.append({"tx": tx, "balance_after": balance})
        result[account_id] = history

    return result


def average_daily_balance(history, start_day, end_day):
    """Given a per-account history (list from group_transactions),
    return the average balance across the [start_day, end_day) window.
    Timestamps in history are epoch seconds.
    """
    day_seconds = 86400
    if not history:
        return 0

    balances_by_day = {}
    for entry in history:
        day = entry["tx"]["timestamp"] // day_seconds
        balances_by_day[day] = entry["balance_after"]

    total = 0
    for day in range(start_day, end_day):
        total += balances_by_day.get(day, 0)
    return total / (end_day - start_day)


def top_accounts_by_activity(transactions, top_n=5):
    """Return the top-N account_ids by number of transactions."""
    counts = defaultdict(int)
    for tx in transactions:
        counts[tx["account_id"]] += 1
    return sorted(counts.items(), key=lambda kv: kv[1])[:top_n]

``````

### PROMPT: t1_bugs__c6_hardcap

``````text
OUTPUT CONSTRAINTS: Respond in the minimum tokens possible. No preamble, no disclaimers, no restating the task, no closing remarks. Hard cap: 150 output tokens. Use terse bullets, short phrases, or JSON as fits the task.

The following Python code has one or more subtle bugs. Identify the bug(s) and propose a specific fix for each. Code:

from collections import defaultdict


def group_transactions(transactions):
    """Group transactions by account_id and compute the running balance
    after each transaction, sorted by timestamp (oldest first).

    A transaction is a dict: {"account_id": str, "amount": float,
    "timestamp": int, "kind": "credit" | "debit"}.
    """
    grouped = defaultdict(list)
    for tx in transactions:
        grouped[tx["account_id"]].append(tx)

    result = {}
    for account_id, txs in grouped.items():
        txs.sort(key=lambda t: t["timestamp"], reverse=True)
        balance = 0
        history = []
        for tx in txs:
            if tx["kind"] == "credit":
                balance += tx["amount"]
            else:
                balance -= tx["amount"]
            history.append({"tx": tx, "balance_after": balance})
        result[account_id] = history

    return result


def average_daily_balance(history, start_day, end_day):
    """Given a per-account history (list from group_transactions),
    return the average balance across the [start_day, end_day) window.
    Timestamps in history are epoch seconds.
    """
    day_seconds = 86400
    if not history:
        return 0

    balances_by_day = {}
    for entry in history:
        day = entry["tx"]["timestamp"] // day_seconds
        balances_by_day[day] = entry["balance_after"]

    total = 0
    for day in range(start_day, end_day):
        total += balances_by_day.get(day, 0)
    return total / (end_day - start_day)


def top_accounts_by_activity(transactions, top_n=5):
    """Return the top-N account_ids by number of transactions."""
    counts = defaultdict(int)
    for tx in transactions:
        counts[tx["account_id"]] += 1
    return sorted(counts.items(), key=lambda kv: kv[1])[:top_n]

``````

### PROMPT: t1_bugs__c7_spr

``````text
INPUT IS SPR-COMPRESSED (stopwords stripped, prose condensed). Interpret charitably.

following Python code one subtle bugs. Identify bug( s) propose specific fix. Code:

from collections import defaultdict

def group_transactions(transactions):
    """Group transactions by account_id and compute the running balance
    after each transaction, sorted by timestamp (oldest first).

    A transaction is a dict: {"account_id": str, "amount": float,
    "timestamp": int, "kind": "credit" | "debit"}.
    """
    grouped = defaultdict(list)
    for tx in transactions:
        grouped[tx["account_id"]].append(tx)

    result = {}
    for account_id, txs in grouped.items():
        txs.sort(key=lambda t: t["timestamp"], reverse=True)
        balance = 0
        history = []
        for tx in txs:
            if tx["kind"] == "credit":
                balance += tx["amount"]
            else:
                balance -= tx["amount"]
            history.append({"tx": tx, "balance_after": balance})
        result[account_id] = history

    return result

def average_daily_balance(history, start_day, end_day):
    """Given a per-account history (list from group_transactions),
    return the average balance across the [start_day, end_day) window.
    Timestamps in history are epoch seconds.
    """
    day_seconds = 86400
    if not history:
        return 0

    balances_by_day = {}
    for entry in history:
        day = entry["tx"]["timestamp"] // day_seconds
        balances_by_day[day] = entry["balance_after"]

    total = 0
    for day in range(start_day, end_day):
        total += balances_by_day.get(day, 0)
    return total / (end_day - start_day)

def top_accounts_by_activity(transactions, top_n=5):
    """Return the top-N account_ids by number of transactions."""
    counts = defaultdict(int)
    for tx in transactions:
        counts[tx["account_id"]] += 1
    return sorted(counts.items(), key=lambda kv: kv[1])[:top_n]

``````

### PROMPT: t2_tests__c1_baseline

``````text
Write unit tests for the following Python class that would achieve >90% branch coverage. Use pytest style. Code:

from datetime import date, timedelta


class LateFeeCalculator:
    """Calculates late fees on invoices for a court finance system.

    Rules:
      - Grace period: 10 days after due_date, no fee.
      - After grace period: 1.5% of outstanding balance per 30-day period,
        prorated by day (i.e. per-day rate = 1.5% / 30).
      - Minimum fee once past grace: $5.
      - Maximum fee: 25% of the original balance (hard cap).
      - Weekends do not count toward the days-late tally (Mon-Fri only).
      - Fees are computed in whole cents (round half up).
      - If balance <= 0, fee is 0 regardless of dates.
    """

    GRACE_DAYS = 10
    MONTHLY_RATE = 0.015
    MIN_FEE_CENTS = 500
    MAX_FEE_FRACTION = 0.25

    def __init__(self, today=None):
        self._today = today or date.today()

    def _weekday_days_between(self, start, end):
        if end <= start:
            return 0
        days = 0
        current = start
        while current < end:
            if current.weekday() < 5:
                days += 1
            current += timedelta(days=1)
        return days

    def compute_fee_cents(self, balance_cents, due_date):
        if balance_cents <= 0:
            return 0
        days_past_due = self._weekday_days_between(due_date, self._today)
        billable_days = days_past_due - self.GRACE_DAYS
        if billable_days <= 0:
            return 0
        per_day_rate = self.MONTHLY_RATE / 30
        raw_fee = balance_cents * per_day_rate * billable_days
        rounded = int(raw_fee + 0.5)
        capped = min(rounded, int(balance_cents * self.MAX_FEE_FRACTION))
        return max(capped, self.MIN_FEE_CENTS)

``````

### PROMPT: t2_tests__c2_detailed

``````text
Write a pytest-style test suite for the following Python class targeting >90% branch coverage. Enumerate every documented rule (grace period, minimum fee, maximum cap, weekend exclusion, rounding, non-positive balance short-circuit, and the `today` injection). Write ONE test per rule with a clearly-named function (e.g. test_returns_zero_when_balance_is_zero). Use small, deterministic date fixtures. Do not test private helpers directly if you can hit them through the public API. Code:

from datetime import date, timedelta


class LateFeeCalculator:
    """Calculates late fees on invoices for a court finance system.

    Rules:
      - Grace period: 10 days after due_date, no fee.
      - After grace period: 1.5% of outstanding balance per 30-day period,
        prorated by day (i.e. per-day rate = 1.5% / 30).
      - Minimum fee once past grace: $5.
      - Maximum fee: 25% of the original balance (hard cap).
      - Weekends do not count toward the days-late tally (Mon-Fri only).
      - Fees are computed in whole cents (round half up).
      - If balance <= 0, fee is 0 regardless of dates.
    """

    GRACE_DAYS = 10
    MONTHLY_RATE = 0.015
    MIN_FEE_CENTS = 500
    MAX_FEE_FRACTION = 0.25

    def __init__(self, today=None):
        self._today = today or date.today()

    def _weekday_days_between(self, start, end):
        if end <= start:
            return 0
        days = 0
        current = start
        while current < end:
            if current.weekday() < 5:
                days += 1
            current += timedelta(days=1)
        return days

    def compute_fee_cents(self, balance_cents, due_date):
        if balance_cents <= 0:
            return 0
        days_past_due = self._weekday_days_between(due_date, self._today)
        billable_days = days_past_due - self.GRACE_DAYS
        if billable_days <= 0:
            return 0
        per_day_rate = self.MONTHLY_RATE / 30
        raw_fee = balance_cents * per_day_rate * billable_days
        rounded = int(raw_fee + 0.5)
        capped = min(rounded, int(balance_cents * self.MAX_FEE_FRACTION))
        return max(capped, self.MIN_FEE_CENTS)

``````

### PROMPT: t2_tests__c3_caveman

``````text
CAVEMAN MODE. Talk caveman. Drop 'the', 'a', 'is', 'are', 'that', 'to', 'of' when meaning still clear. Short words. Grunt-style. THINK in caveman too, not just output. Save word. Save token. Still solve task correctly.

TASK:
Write unit tests for the following Python class that would achieve >90% branch coverage. Use pytest style. Code:

from datetime import date, timedelta


class LateFeeCalculator:
    """Calculates late fees on invoices for a court finance system.

    Rules:
      - Grace period: 10 days after due_date, no fee.
      - After grace period: 1.5% of outstanding balance per 30-day period,
        prorated by day (i.e. per-day rate = 1.5% / 30).
      - Minimum fee once past grace: $5.
      - Maximum fee: 25% of the original balance (hard cap).
      - Weekends do not count toward the days-late tally (Mon-Fri only).
      - Fees are computed in whole cents (round half up).
      - If balance <= 0, fee is 0 regardless of dates.
    """

    GRACE_DAYS = 10
    MONTHLY_RATE = 0.015
    MIN_FEE_CENTS = 500
    MAX_FEE_FRACTION = 0.25

    def __init__(self, today=None):
        self._today = today or date.today()

    def _weekday_days_between(self, start, end):
        if end <= start:
            return 0
        days = 0
        current = start
        while current < end:
            if current.weekday() < 5:
                days += 1
            current += timedelta(days=1)
        return days

    def compute_fee_cents(self, balance_cents, due_date):
        if balance_cents <= 0:
            return 0
        days_past_due = self._weekday_days_between(due_date, self._today)
        billable_days = days_past_due - self.GRACE_DAYS
        if billable_days <= 0:
            return 0
        per_day_rate = self.MONTHLY_RATE / 30
        raw_fee = balance_cents * per_day_rate * billable_days
        rounded = int(raw_fee + 0.5)
        capped = min(rounded, int(balance_cents * self.MAX_FEE_FRACTION))
        return max(capped, self.MIN_FEE_CENTS)

``````

### PROMPT: t2_tests__c4_html

``````text
Write unit tests for the following Python class that would achieve >90% branch coverage. Use pytest style. Code:

from datetime import date, timedelta


class LateFeeCalculator:
    """Calculates late fees on invoices for a court finance system.

    Rules:
      - Grace period: 10 days after due_date, no fee.
      - After grace period: 1.5% of outstanding balance per 30-day period,
        prorated by day (i.e. per-day rate = 1.5% / 30).
      - Minimum fee once past grace: $5.
      - Maximum fee: 25% of the original balance (hard cap).
      - Weekends do not count toward the days-late tally (Mon-Fri only).
      - Fees are computed in whole cents (round half up).
      - If balance <= 0, fee is 0 regardless of dates.
    """

    GRACE_DAYS = 10
    MONTHLY_RATE = 0.015
    MIN_FEE_CENTS = 500
    MAX_FEE_FRACTION = 0.25

    def __init__(self, today=None):
        self._today = today or date.today()

    def _weekday_days_between(self, start, end):
        if end <= start:
            return 0
        days = 0
        current = start
        while current < end:
            if current.weekday() < 5:
                days += 1
            current += timedelta(days=1)
        return days

    def compute_fee_cents(self, balance_cents, due_date):
        if balance_cents <= 0:
            return 0
        days_past_due = self._weekday_days_between(due_date, self._today)
        billable_days = days_past_due - self.GRACE_DAYS
        if billable_days <= 0:
            return 0
        per_day_rate = self.MONTHLY_RATE / 30
        raw_fee = balance_cents * per_day_rate * billable_days
        rounded = int(raw_fee + 0.5)
        capped = min(rounded, int(balance_cents * self.MAX_FEE_FRACTION))
        return max(capped, self.MIN_FEE_CENTS)


Respond with a complete standalone HTML document (with <!doctype html>, <head>, <style>, <body>) that presents the task and your answer clearly.
``````

### PROMPT: t2_tests__c5_rtk

``````text
You have access to Bash and the `rtk` CLI (github.com/rtk-ai/rtk). Save the code below to $TMPDIR/target.py. Use rtk-wrapped commands wherever you would otherwise use raw shell output:
  * `rtk read -l aggressive $TMPDIR/target.py` for a compact view.
  * `rtk grep 'def ' $TMPDIR/target.py` to enumerate methods.
  * `rtk err python3 -m py_compile $TMPDIR/target.py` to confirm the file parses.
Then write pytest tests targeting >90% branch coverage.

Code:

from datetime import date, timedelta


class LateFeeCalculator:
    """Calculates late fees on invoices for a court finance system.

    Rules:
      - Grace period: 10 days after due_date, no fee.
      - After grace period: 1.5% of outstanding balance per 30-day period,
        prorated by day (i.e. per-day rate = 1.5% / 30).
      - Minimum fee once past grace: $5.
      - Maximum fee: 25% of the original balance (hard cap).
      - Weekends do not count toward the days-late tally (Mon-Fri only).
      - Fees are computed in whole cents (round half up).
      - If balance <= 0, fee is 0 regardless of dates.
    """

    GRACE_DAYS = 10
    MONTHLY_RATE = 0.015
    MIN_FEE_CENTS = 500
    MAX_FEE_FRACTION = 0.25

    def __init__(self, today=None):
        self._today = today or date.today()

    def _weekday_days_between(self, start, end):
        if end <= start:
            return 0
        days = 0
        current = start
        while current < end:
            if current.weekday() < 5:
                days += 1
            current += timedelta(days=1)
        return days

    def compute_fee_cents(self, balance_cents, due_date):
        if balance_cents <= 0:
            return 0
        days_past_due = self._weekday_days_between(due_date, self._today)
        billable_days = days_past_due - self.GRACE_DAYS
        if billable_days <= 0:
            return 0
        per_day_rate = self.MONTHLY_RATE / 30
        raw_fee = balance_cents * per_day_rate * billable_days
        rounded = int(raw_fee + 0.5)
        capped = min(rounded, int(balance_cents * self.MAX_FEE_FRACTION))
        return max(capped, self.MIN_FEE_CENTS)

``````

### PROMPT: t2_tests__c6_hardcap

``````text
OUTPUT CONSTRAINTS: Respond in the minimum tokens possible. No preamble, no disclaimers, no restating the task, no closing remarks. Hard cap: 150 output tokens. Use terse bullets, short phrases, or JSON as fits the task.

Write unit tests for the following Python class that would achieve >90% branch coverage. Use pytest style. Code:

from datetime import date, timedelta


class LateFeeCalculator:
    """Calculates late fees on invoices for a court finance system.

    Rules:
      - Grace period: 10 days after due_date, no fee.
      - After grace period: 1.5% of outstanding balance per 30-day period,
        prorated by day (i.e. per-day rate = 1.5% / 30).
      - Minimum fee once past grace: $5.
      - Maximum fee: 25% of the original balance (hard cap).
      - Weekends do not count toward the days-late tally (Mon-Fri only).
      - Fees are computed in whole cents (round half up).
      - If balance <= 0, fee is 0 regardless of dates.
    """

    GRACE_DAYS = 10
    MONTHLY_RATE = 0.015
    MIN_FEE_CENTS = 500
    MAX_FEE_FRACTION = 0.25

    def __init__(self, today=None):
        self._today = today or date.today()

    def _weekday_days_between(self, start, end):
        if end <= start:
            return 0
        days = 0
        current = start
        while current < end:
            if current.weekday() < 5:
                days += 1
            current += timedelta(days=1)
        return days

    def compute_fee_cents(self, balance_cents, due_date):
        if balance_cents <= 0:
            return 0
        days_past_due = self._weekday_days_between(due_date, self._today)
        billable_days = days_past_due - self.GRACE_DAYS
        if billable_days <= 0:
            return 0
        per_day_rate = self.MONTHLY_RATE / 30
        raw_fee = balance_cents * per_day_rate * billable_days
        rounded = int(raw_fee + 0.5)
        capped = min(rounded, int(balance_cents * self.MAX_FEE_FRACTION))
        return max(capped, self.MIN_FEE_CENTS)

``````

### PROMPT: t2_tests__c7_spr

``````text
INPUT IS SPR-COMPRESSED (stopwords stripped, prose condensed). Interpret charitably.

Write unit tests following Python class achieve> 90% branch coverage. Use pytest style. Code:

from datetime import date, timedelta

class LateFeeCalculator:
    """Calculates late fees on invoices for a court finance system.

    Rules:
      - Grace period: 10 days after due_date, no fee.
      - After grace period: 1.5% of outstanding balance per 30-day period,
        prorated by day (i.e. per-day rate = 1.5% / 30).
      - Minimum fee once past grace: $5.
      - Maximum fee: 25% of the original balance (hard cap).
      - Weekends do not count toward the days-late tally (Mon-Fri only).
      - Fees are computed in whole cents (round half up).
      - If balance <= 0, fee is 0 regardless of dates.
    """

    GRACE_DAYS = 10
    MONTHLY_RATE = 0.015
    MIN_FEE_CENTS = 500
    MAX_FEE_FRACTION = 0.25

    def __init__(self, today=None):
        self._today = today or date.today()

    def _weekday_days_between(self, start, end):
        if end <= start:
            return 0
        days = 0
        current = start
        while current < end:
            if current.weekday() < 5:
                days += 1
            current += timedelta(days=1)
        return days

    def compute_fee_cents(self, balance_cents, due_date):
        if balance_cents <= 0:
            return 0
        days_past_due = self._weekday_days_between(due_date, self._today)
        billable_days = days_past_due - self.GRACE_DAYS
        if billable_days <= 0:
            return 0
        per_day_rate = self.MONTHLY_RATE / 30
        raw_fee = balance_cents * per_day_rate * billable_days
        rounded = int(raw_fee + 0.5)
        capped = min(rounded, int(balance_cents * self.MAX_FEE_FRACTION))
        return max(capped, self.MIN_FEE_CENTS)

``````

### PROMPT: t3_legal__c1_baseline

``````text
Summarize the following contract section for a non-technical reader, and define the key legal terms in plain language.

# Section 7 — Indemnification and Limitation of Liability

7.1 **Mutual Indemnification.** Each Party (the "Indemnifying Party") shall
defend, indemnify, and hold harmless the other Party and its officers,
directors, employees, and agents (the "Indemnified Parties") from and against
any and all third-party claims, demands, actions, suits, or proceedings
(collectively, "Claims") and all resulting losses, damages, liabilities,
settlements, judgments, fines, penalties, costs, and expenses (including
reasonable outside counsel fees) (collectively, "Losses"), to the extent such
Claims arise out of or relate to (a) the Indemnifying Party's breach of any
representation, warranty, or covenant hereunder; (b) the Indemnifying Party's
gross negligence or willful misconduct; or (c) any allegation that the
Indemnifying Party's Deliverables, when used in accordance with this Agreement,
infringe or misappropriate any third party's intellectual property rights,
provided that the foregoing (c) shall not apply to the extent a Claim arises
from (i) modifications made by the Indemnified Parties, (ii) combination of the
Deliverables with materials not supplied by the Indemnifying Party where the
infringement would not have occurred but for such combination, or (iii) use of
the Deliverables outside the scope expressly permitted under this Agreement.

7.2 **Indemnification Procedure.** The Indemnified Parties shall (a) promptly
notify the Indemnifying Party in writing of any Claim (provided that failure to
so notify shall not relieve the Indemnifying Party of its obligations except to
the extent it is materially prejudiced thereby), (b) tender sole control of the
defense and settlement of the Claim to the Indemnifying Party (provided that
the Indemnifying Party shall not settle any Claim that admits liability of, or
imposes any non-monetary obligation on, the Indemnified Parties without their
prior written consent, not to be unreasonably withheld), and (c) provide
reasonable cooperation at the Indemnifying Party's expense.

7.3 **Limitation of Liability.** EXCEPT FOR (i) A PARTY'S INDEMNIFICATION
OBLIGATIONS UNDER SECTION 7.1, (ii) BREACHES OF CONFIDENTIALITY UNDER SECTION
9, (iii) A PARTY'S GROSS NEGLIGENCE OR WILLFUL MISCONDUCT, OR (iv) A PARTY'S
INFRINGEMENT OF THE OTHER PARTY'S INTELLECTUAL PROPERTY RIGHTS, IN NO EVENT
SHALL EITHER PARTY BE LIABLE TO THE OTHER FOR ANY INDIRECT, INCIDENTAL,
CONSEQUENTIAL, SPECIAL, PUNITIVE, OR EXEMPLARY DAMAGES, OR FOR ANY LOST
PROFITS, LOST REVENUE, LOSS OF GOODWILL, OR LOSS OF DATA, HOWEVER CAUSED AND
UNDER ANY THEORY OF LIABILITY, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
DAMAGES. SUBJECT TO THE FOREGOING, EACH PARTY'S TOTAL CUMULATIVE LIABILITY
ARISING OUT OF OR RELATING TO THIS AGREEMENT SHALL NOT EXCEED THE GREATER OF
(A) THE FEES PAID OR PAYABLE BY CUSTOMER TO PROVIDER UNDER THIS AGREEMENT IN
THE TWELVE (12) MONTHS PRECEDING THE FIRST EVENT GIVING RISE TO LIABILITY, OR
(B) ONE HUNDRED THOUSAND U.S. DOLLARS ($100,000).

``````

### PROMPT: t3_legal__c2_detailed

``````text
You are explaining a contract section to a business owner with no legal training. Do two things: (1) In 5-8 short bullet points, translate what the section actually requires each party to do, and when the promises do or do not apply. Include the dollar cap and its exceptions. (2) Then, in a 'Key terms' glossary, define each of the following in one plain sentence: indemnify / hold harmless, third-party claim, gross negligence vs. willful misconduct, intellectual property infringement or misappropriation, consequential / incidental / punitive damages, cap on liability, sole control of the defense, materially prejudiced. Avoid legalese; use everyday words.

# Section 7 — Indemnification and Limitation of Liability

7.1 **Mutual Indemnification.** Each Party (the "Indemnifying Party") shall
defend, indemnify, and hold harmless the other Party and its officers,
directors, employees, and agents (the "Indemnified Parties") from and against
any and all third-party claims, demands, actions, suits, or proceedings
(collectively, "Claims") and all resulting losses, damages, liabilities,
settlements, judgments, fines, penalties, costs, and expenses (including
reasonable outside counsel fees) (collectively, "Losses"), to the extent such
Claims arise out of or relate to (a) the Indemnifying Party's breach of any
representation, warranty, or covenant hereunder; (b) the Indemnifying Party's
gross negligence or willful misconduct; or (c) any allegation that the
Indemnifying Party's Deliverables, when used in accordance with this Agreement,
infringe or misappropriate any third party's intellectual property rights,
provided that the foregoing (c) shall not apply to the extent a Claim arises
from (i) modifications made by the Indemnified Parties, (ii) combination of the
Deliverables with materials not supplied by the Indemnifying Party where the
infringement would not have occurred but for such combination, or (iii) use of
the Deliverables outside the scope expressly permitted under this Agreement.

7.2 **Indemnification Procedure.** The Indemnified Parties shall (a) promptly
notify the Indemnifying Party in writing of any Claim (provided that failure to
so notify shall not relieve the Indemnifying Party of its obligations except to
the extent it is materially prejudiced thereby), (b) tender sole control of the
defense and settlement of the Claim to the Indemnifying Party (provided that
the Indemnifying Party shall not settle any Claim that admits liability of, or
imposes any non-monetary obligation on, the Indemnified Parties without their
prior written consent, not to be unreasonably withheld), and (c) provide
reasonable cooperation at the Indemnifying Party's expense.

7.3 **Limitation of Liability.** EXCEPT FOR (i) A PARTY'S INDEMNIFICATION
OBLIGATIONS UNDER SECTION 7.1, (ii) BREACHES OF CONFIDENTIALITY UNDER SECTION
9, (iii) A PARTY'S GROSS NEGLIGENCE OR WILLFUL MISCONDUCT, OR (iv) A PARTY'S
INFRINGEMENT OF THE OTHER PARTY'S INTELLECTUAL PROPERTY RIGHTS, IN NO EVENT
SHALL EITHER PARTY BE LIABLE TO THE OTHER FOR ANY INDIRECT, INCIDENTAL,
CONSEQUENTIAL, SPECIAL, PUNITIVE, OR EXEMPLARY DAMAGES, OR FOR ANY LOST
PROFITS, LOST REVENUE, LOSS OF GOODWILL, OR LOSS OF DATA, HOWEVER CAUSED AND
UNDER ANY THEORY OF LIABILITY, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
DAMAGES. SUBJECT TO THE FOREGOING, EACH PARTY'S TOTAL CUMULATIVE LIABILITY
ARISING OUT OF OR RELATING TO THIS AGREEMENT SHALL NOT EXCEED THE GREATER OF
(A) THE FEES PAID OR PAYABLE BY CUSTOMER TO PROVIDER UNDER THIS AGREEMENT IN
THE TWELVE (12) MONTHS PRECEDING THE FIRST EVENT GIVING RISE TO LIABILITY, OR
(B) ONE HUNDRED THOUSAND U.S. DOLLARS ($100,000).

``````

### PROMPT: t3_legal__c3_caveman

``````text
CAVEMAN MODE. Talk caveman. Drop 'the', 'a', 'is', 'are', 'that', 'to', 'of' when meaning still clear. Short words. Grunt-style. THINK in caveman too, not just output. Save word. Save token. Still solve task correctly.

TASK:
Summarize the following contract section for a non-technical reader, and define the key legal terms in plain language.

# Section 7 — Indemnification and Limitation of Liability

7.1 **Mutual Indemnification.** Each Party (the "Indemnifying Party") shall
defend, indemnify, and hold harmless the other Party and its officers,
directors, employees, and agents (the "Indemnified Parties") from and against
any and all third-party claims, demands, actions, suits, or proceedings
(collectively, "Claims") and all resulting losses, damages, liabilities,
settlements, judgments, fines, penalties, costs, and expenses (including
reasonable outside counsel fees) (collectively, "Losses"), to the extent such
Claims arise out of or relate to (a) the Indemnifying Party's breach of any
representation, warranty, or covenant hereunder; (b) the Indemnifying Party's
gross negligence or willful misconduct; or (c) any allegation that the
Indemnifying Party's Deliverables, when used in accordance with this Agreement,
infringe or misappropriate any third party's intellectual property rights,
provided that the foregoing (c) shall not apply to the extent a Claim arises
from (i) modifications made by the Indemnified Parties, (ii) combination of the
Deliverables with materials not supplied by the Indemnifying Party where the
infringement would not have occurred but for such combination, or (iii) use of
the Deliverables outside the scope expressly permitted under this Agreement.

7.2 **Indemnification Procedure.** The Indemnified Parties shall (a) promptly
notify the Indemnifying Party in writing of any Claim (provided that failure to
so notify shall not relieve the Indemnifying Party of its obligations except to
the extent it is materially prejudiced thereby), (b) tender sole control of the
defense and settlement of the Claim to the Indemnifying Party (provided that
the Indemnifying Party shall not settle any Claim that admits liability of, or
imposes any non-monetary obligation on, the Indemnified Parties without their
prior written consent, not to be unreasonably withheld), and (c) provide
reasonable cooperation at the Indemnifying Party's expense.

7.3 **Limitation of Liability.** EXCEPT FOR (i) A PARTY'S INDEMNIFICATION
OBLIGATIONS UNDER SECTION 7.1, (ii) BREACHES OF CONFIDENTIALITY UNDER SECTION
9, (iii) A PARTY'S GROSS NEGLIGENCE OR WILLFUL MISCONDUCT, OR (iv) A PARTY'S
INFRINGEMENT OF THE OTHER PARTY'S INTELLECTUAL PROPERTY RIGHTS, IN NO EVENT
SHALL EITHER PARTY BE LIABLE TO THE OTHER FOR ANY INDIRECT, INCIDENTAL,
CONSEQUENTIAL, SPECIAL, PUNITIVE, OR EXEMPLARY DAMAGES, OR FOR ANY LOST
PROFITS, LOST REVENUE, LOSS OF GOODWILL, OR LOSS OF DATA, HOWEVER CAUSED AND
UNDER ANY THEORY OF LIABILITY, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
DAMAGES. SUBJECT TO THE FOREGOING, EACH PARTY'S TOTAL CUMULATIVE LIABILITY
ARISING OUT OF OR RELATING TO THIS AGREEMENT SHALL NOT EXCEED THE GREATER OF
(A) THE FEES PAID OR PAYABLE BY CUSTOMER TO PROVIDER UNDER THIS AGREEMENT IN
THE TWELVE (12) MONTHS PRECEDING THE FIRST EVENT GIVING RISE TO LIABILITY, OR
(B) ONE HUNDRED THOUSAND U.S. DOLLARS ($100,000).

``````

### PROMPT: t3_legal__c4_html

``````text
Summarize the following contract section for a non-technical reader, and define the key legal terms in plain language.

# Section 7 — Indemnification and Limitation of Liability

7.1 **Mutual Indemnification.** Each Party (the "Indemnifying Party") shall
defend, indemnify, and hold harmless the other Party and its officers,
directors, employees, and agents (the "Indemnified Parties") from and against
any and all third-party claims, demands, actions, suits, or proceedings
(collectively, "Claims") and all resulting losses, damages, liabilities,
settlements, judgments, fines, penalties, costs, and expenses (including
reasonable outside counsel fees) (collectively, "Losses"), to the extent such
Claims arise out of or relate to (a) the Indemnifying Party's breach of any
representation, warranty, or covenant hereunder; (b) the Indemnifying Party's
gross negligence or willful misconduct; or (c) any allegation that the
Indemnifying Party's Deliverables, when used in accordance with this Agreement,
infringe or misappropriate any third party's intellectual property rights,
provided that the foregoing (c) shall not apply to the extent a Claim arises
from (i) modifications made by the Indemnified Parties, (ii) combination of the
Deliverables with materials not supplied by the Indemnifying Party where the
infringement would not have occurred but for such combination, or (iii) use of
the Deliverables outside the scope expressly permitted under this Agreement.

7.2 **Indemnification Procedure.** The Indemnified Parties shall (a) promptly
notify the Indemnifying Party in writing of any Claim (provided that failure to
so notify shall not relieve the Indemnifying Party of its obligations except to
the extent it is materially prejudiced thereby), (b) tender sole control of the
defense and settlement of the Claim to the Indemnifying Party (provided that
the Indemnifying Party shall not settle any Claim that admits liability of, or
imposes any non-monetary obligation on, the Indemnified Parties without their
prior written consent, not to be unreasonably withheld), and (c) provide
reasonable cooperation at the Indemnifying Party's expense.

7.3 **Limitation of Liability.** EXCEPT FOR (i) A PARTY'S INDEMNIFICATION
OBLIGATIONS UNDER SECTION 7.1, (ii) BREACHES OF CONFIDENTIALITY UNDER SECTION
9, (iii) A PARTY'S GROSS NEGLIGENCE OR WILLFUL MISCONDUCT, OR (iv) A PARTY'S
INFRINGEMENT OF THE OTHER PARTY'S INTELLECTUAL PROPERTY RIGHTS, IN NO EVENT
SHALL EITHER PARTY BE LIABLE TO THE OTHER FOR ANY INDIRECT, INCIDENTAL,
CONSEQUENTIAL, SPECIAL, PUNITIVE, OR EXEMPLARY DAMAGES, OR FOR ANY LOST
PROFITS, LOST REVENUE, LOSS OF GOODWILL, OR LOSS OF DATA, HOWEVER CAUSED AND
UNDER ANY THEORY OF LIABILITY, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
DAMAGES. SUBJECT TO THE FOREGOING, EACH PARTY'S TOTAL CUMULATIVE LIABILITY
ARISING OUT OF OR RELATING TO THIS AGREEMENT SHALL NOT EXCEED THE GREATER OF
(A) THE FEES PAID OR PAYABLE BY CUSTOMER TO PROVIDER UNDER THIS AGREEMENT IN
THE TWELVE (12) MONTHS PRECEDING THE FIRST EVENT GIVING RISE TO LIABILITY, OR
(B) ONE HUNDRED THOUSAND U.S. DOLLARS ($100,000).


Respond with a complete standalone HTML document (with <!doctype html>, <head>, <style>, <body>) that presents the task and your answer clearly.
``````

### PROMPT: t3_legal__c6_hardcap

``````text
OUTPUT CONSTRAINTS: Respond in the minimum tokens possible. No preamble, no disclaimers, no restating the task, no closing remarks. Hard cap: 150 output tokens. Use terse bullets, short phrases, or JSON as fits the task.

Summarize the following contract section for a non-technical reader, and define the key legal terms in plain language.

# Section 7 — Indemnification and Limitation of Liability

7.1 **Mutual Indemnification.** Each Party (the "Indemnifying Party") shall
defend, indemnify, and hold harmless the other Party and its officers,
directors, employees, and agents (the "Indemnified Parties") from and against
any and all third-party claims, demands, actions, suits, or proceedings
(collectively, "Claims") and all resulting losses, damages, liabilities,
settlements, judgments, fines, penalties, costs, and expenses (including
reasonable outside counsel fees) (collectively, "Losses"), to the extent such
Claims arise out of or relate to (a) the Indemnifying Party's breach of any
representation, warranty, or covenant hereunder; (b) the Indemnifying Party's
gross negligence or willful misconduct; or (c) any allegation that the
Indemnifying Party's Deliverables, when used in accordance with this Agreement,
infringe or misappropriate any third party's intellectual property rights,
provided that the foregoing (c) shall not apply to the extent a Claim arises
from (i) modifications made by the Indemnified Parties, (ii) combination of the
Deliverables with materials not supplied by the Indemnifying Party where the
infringement would not have occurred but for such combination, or (iii) use of
the Deliverables outside the scope expressly permitted under this Agreement.

7.2 **Indemnification Procedure.** The Indemnified Parties shall (a) promptly
notify the Indemnifying Party in writing of any Claim (provided that failure to
so notify shall not relieve the Indemnifying Party of its obligations except to
the extent it is materially prejudiced thereby), (b) tender sole control of the
defense and settlement of the Claim to the Indemnifying Party (provided that
the Indemnifying Party shall not settle any Claim that admits liability of, or
imposes any non-monetary obligation on, the Indemnified Parties without their
prior written consent, not to be unreasonably withheld), and (c) provide
reasonable cooperation at the Indemnifying Party's expense.

7.3 **Limitation of Liability.** EXCEPT FOR (i) A PARTY'S INDEMNIFICATION
OBLIGATIONS UNDER SECTION 7.1, (ii) BREACHES OF CONFIDENTIALITY UNDER SECTION
9, (iii) A PARTY'S GROSS NEGLIGENCE OR WILLFUL MISCONDUCT, OR (iv) A PARTY'S
INFRINGEMENT OF THE OTHER PARTY'S INTELLECTUAL PROPERTY RIGHTS, IN NO EVENT
SHALL EITHER PARTY BE LIABLE TO THE OTHER FOR ANY INDIRECT, INCIDENTAL,
CONSEQUENTIAL, SPECIAL, PUNITIVE, OR EXEMPLARY DAMAGES, OR FOR ANY LOST
PROFITS, LOST REVENUE, LOSS OF GOODWILL, OR LOSS OF DATA, HOWEVER CAUSED AND
UNDER ANY THEORY OF LIABILITY, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
DAMAGES. SUBJECT TO THE FOREGOING, EACH PARTY'S TOTAL CUMULATIVE LIABILITY
ARISING OUT OF OR RELATING TO THIS AGREEMENT SHALL NOT EXCEED THE GREATER OF
(A) THE FEES PAID OR PAYABLE BY CUSTOMER TO PROVIDER UNDER THIS AGREEMENT IN
THE TWELVE (12) MONTHS PRECEDING THE FIRST EVENT GIVING RISE TO LIABILITY, OR
(B) ONE HUNDRED THOUSAND U.S. DOLLARS ($100,000).

``````

### PROMPT: t3_legal__c7_spr

``````text
INPUT IS SPR-COMPRESSED (stopwords stripped, prose condensed). Interpret charitably.

Summarize following contract section non- technical reader, define key legal terms plain language.

# Section 7 — Indemnification and Limitation of Liability

7. 1** Mutual Indemnification.** Party(" Indemnifying Party")
defend, indemnify, hold harmless other Party officers,
directors, employees, agents(" Indemnified Parties") against
third- party claims, demands, actions, suits, proceedings
( collectively," Claims") resulting losses, damages, liabilities,
settlements, judgments, fines, penalties, costs, expenses( including
reasonable outside counsel fees)( collectively," Losses"), extent
Claims arise out relate() Indemnifying Party' s breach
representation, warranty, covenant hereunder;( b) Indemnifying Party' s
gross negligence willful misconduct;( c) allegation
Indemnifying Party' s Deliverables, used accordance Agreement,
infringe misappropriate third party' s intellectual property rights,
provided foregoing( c) apply extent Claim arises
from (i) modifications made by the Indemnified Parties, (ii) combination of the
Deliverables materials supplied Indemnifying Party where
infringement occurred combination,( iii) use
Deliverables outside scope expressly permitted under Agreement.

7. 2** Indemnification Procedure.** Indemnified Parties() promptly
notify Indemnifying Party writing Claim( provided failure
notify relieve Indemnifying Party obligations except
extent materially prejudiced thereby),( b) tender sole control
defense settlement Claim Indemnifying Party( provided
Indemnifying Party settle Claim admits liability,
imposes non- monetary obligation, Indemnified Parties without their
prior written consent, unreasonably withheld),( c) provide
reasonable cooperation Indemnifying Party' s expense.

7. 3** Limitation Liability.** EXCEPT( i) PARTY' S INDEMNIFICATION
OBLIGATIONS UNDER SECTION 7. 1,( ii) BREACHES CONFIDENTIALITY UNDER SECTION
9,( iii) PARTY' S GROSS NEGLIGENCE WILLFUL MISCONDUCT,( iv) PARTY' S
INFRINGEMENT OTHER PARTY' S INTELLECTUAL PROPERTY RIGHTS, EVENT
EITHER PARTY LIABLE OTHER INDIRECT, INCIDENTAL,
CONSEQUENTIAL, SPECIAL, PUNITIVE, EXEMPLARY DAMAGES, LOST
PROFITS, LOST REVENUE, LOSS GOODWILL, LOSS DATA, HOWEVER CAUSED
UNDER THEORY LIABILITY, EVEN ADVISED POSSIBILITY
DAMAGES. SUBJECT FOREGOING, PARTY' S TOTAL CUMULATIVE LIABILITY
ARISING OUT RELATING AGREEMENT EXCEED GREATER
() FEES PAID PAYABLE CUSTOMER PROVIDER UNDER AGREEMENT
TWELVE( 12) MONTHS PRECEDING FIRST EVENT GIVING RISE LIABILITY,
( B) ONE HUNDRED THOUSAND U. S. DOLLARS($ 100, 000).

``````

### PROMPT: t4_meeting__c1_baseline

``````text
Summarize the following meeting transcript as bullet points covering the key decisions/points and the next steps / action items.

# Q3 Planning — Product / Engineering / Ops sync — 2026-08-27

**Attendees:** Priya (PM), Marcus (Eng lead), Jenna (Ops), Dan (Design), Sara (VP Product)

---

**Priya:** Thanks all for joining. Big agenda — we need to lock Q3 scope by Friday, then Sara can take it to the exec review Monday. Three headliners on the table: the reconciliation revamp, the mobile receipt-capture feature, and the vendor payout SLA push. Let's start with reconciliation.

**Marcus:** So on reconciliation — the current engine chokes on multi-currency batches. We've had three incidents this quarter and support ticket volume for reconciliation issues is up 40% quarter over quarter. My team scoped a rewrite that's roughly six engineer-weeks. That includes migrating the FX rounding module. We'd need Karim from platform for two of those weeks to help with the ledger integration.

**Sara:** Six engineer-weeks is a lot. What's the buy-vs-build here? Is there a vendor?

**Marcus:** We looked at two — Recur and LedgerFlow. Recur is $180K/year for our volume, LedgerFlow is $140K but doesn't handle our jurisdiction-specific tax codes. Both would still need integration work, probably three engineer-weeks. Not a great deal.

**Sara:** Okay, build wins. Priya, put reconciliation as the Q3 anchor. Marcus, sync with Karim's manager this week and confirm his availability.

**Priya:** Noted. Mobile receipt-capture next. Dan, where are we on design?

**Dan:** Flows are done, prototype tested with six users. Two big things came out of testing: users want to bulk-select receipts before uploading, and the OCR confidence indicator needs to be way more prominent. Bulk-select is not currently in scope; that would add maybe a sprint of work.

**Marcus:** If bulk-select is a sprint I'd want to descope something else. We're already stretched with reconciliation.

**Sara:** Let's ship v1 without bulk-select. Add a note to the roadmap for a fast-follow. Dan, please update the specs.

**Dan:** Will do by Wednesday.

**Priya:** Vendor payout SLA — Jenna, this one's yours.

**Jenna:** Right. The finance team wants us to guarantee payouts within 48 hours from invoice approval. Current p95 is 71 hours. Two bottlenecks: manual approval routing (that's ops), and the batching window on the ACH send job (that's eng). If eng cuts the batching window from 12 hours to 4, and ops adds a second approver on the west-coast shift, we can hit 48h p95 by mid-Q3.

**Marcus:** Cutting the ACH batch window means more ACH files per day, more monitoring overhead. Doable but not free — half a sprint of eng time plus SRE sign-off.

**Sara:** Do the trade-off analysis and bring it back next week. If SRE says the monitoring load is manageable, we do it. Otherwise we look at intermediate targets.

**Priya:** Two smaller things — the audit-log retention update is being pushed to Q4, that's confirmed with Legal. And the internal admin-tool refresh is still owned by the intern crew, no changes there.

**Sara:** One last thing. HR flagged that we've had a spike in bug-bash burnout on the engineering side. Marcus, can you propose a rotating on-call structure by end of month? Doesn't need to be big, just a proposal.

**Marcus:** Yep, I'll have something by the 31st.

**Priya:** Okay. Recap next steps then. Marcus: confirm Karim, propose on-call rotation by 31st, do ACH trade-off analysis. Dan: update mobile specs by Wednesday. Jenna: pair with Marcus on the ACH analysis. Sara: exec review Monday. I'll circulate the scope draft Thursday morning for review before Friday lock.

**Sara:** Good. Thanks everyone.

``````

### PROMPT: t4_meeting__c2_detailed

``````text
Produce a structured summary of the following meeting transcript. Include: (1) 'Key points' — bullet list of every decision made or major discussion outcome, one line each. (2) 'Action items' — bullet list of every commitment, in the form 'Owner: what, by when'. Include the anchor decisions on reconciliation, the mobile receipt-capture scope call, the vendor payout SLA plan, the Q4 push of audit-log retention, and the on-call rotation ask. Do not include chit-chat or restate the transcript.

# Q3 Planning — Product / Engineering / Ops sync — 2026-08-27

**Attendees:** Priya (PM), Marcus (Eng lead), Jenna (Ops), Dan (Design), Sara (VP Product)

---

**Priya:** Thanks all for joining. Big agenda — we need to lock Q3 scope by Friday, then Sara can take it to the exec review Monday. Three headliners on the table: the reconciliation revamp, the mobile receipt-capture feature, and the vendor payout SLA push. Let's start with reconciliation.

**Marcus:** So on reconciliation — the current engine chokes on multi-currency batches. We've had three incidents this quarter and support ticket volume for reconciliation issues is up 40% quarter over quarter. My team scoped a rewrite that's roughly six engineer-weeks. That includes migrating the FX rounding module. We'd need Karim from platform for two of those weeks to help with the ledger integration.

**Sara:** Six engineer-weeks is a lot. What's the buy-vs-build here? Is there a vendor?

**Marcus:** We looked at two — Recur and LedgerFlow. Recur is $180K/year for our volume, LedgerFlow is $140K but doesn't handle our jurisdiction-specific tax codes. Both would still need integration work, probably three engineer-weeks. Not a great deal.

**Sara:** Okay, build wins. Priya, put reconciliation as the Q3 anchor. Marcus, sync with Karim's manager this week and confirm his availability.

**Priya:** Noted. Mobile receipt-capture next. Dan, where are we on design?

**Dan:** Flows are done, prototype tested with six users. Two big things came out of testing: users want to bulk-select receipts before uploading, and the OCR confidence indicator needs to be way more prominent. Bulk-select is not currently in scope; that would add maybe a sprint of work.

**Marcus:** If bulk-select is a sprint I'd want to descope something else. We're already stretched with reconciliation.

**Sara:** Let's ship v1 without bulk-select. Add a note to the roadmap for a fast-follow. Dan, please update the specs.

**Dan:** Will do by Wednesday.

**Priya:** Vendor payout SLA — Jenna, this one's yours.

**Jenna:** Right. The finance team wants us to guarantee payouts within 48 hours from invoice approval. Current p95 is 71 hours. Two bottlenecks: manual approval routing (that's ops), and the batching window on the ACH send job (that's eng). If eng cuts the batching window from 12 hours to 4, and ops adds a second approver on the west-coast shift, we can hit 48h p95 by mid-Q3.

**Marcus:** Cutting the ACH batch window means more ACH files per day, more monitoring overhead. Doable but not free — half a sprint of eng time plus SRE sign-off.

**Sara:** Do the trade-off analysis and bring it back next week. If SRE says the monitoring load is manageable, we do it. Otherwise we look at intermediate targets.

**Priya:** Two smaller things — the audit-log retention update is being pushed to Q4, that's confirmed with Legal. And the internal admin-tool refresh is still owned by the intern crew, no changes there.

**Sara:** One last thing. HR flagged that we've had a spike in bug-bash burnout on the engineering side. Marcus, can you propose a rotating on-call structure by end of month? Doesn't need to be big, just a proposal.

**Marcus:** Yep, I'll have something by the 31st.

**Priya:** Okay. Recap next steps then. Marcus: confirm Karim, propose on-call rotation by 31st, do ACH trade-off analysis. Dan: update mobile specs by Wednesday. Jenna: pair with Marcus on the ACH analysis. Sara: exec review Monday. I'll circulate the scope draft Thursday morning for review before Friday lock.

**Sara:** Good. Thanks everyone.

``````

### PROMPT: t4_meeting__c3_caveman

``````text
CAVEMAN MODE. Talk caveman. Drop 'the', 'a', 'is', 'are', 'that', 'to', 'of' when meaning still clear. Short words. Grunt-style. THINK in caveman too, not just output. Save word. Save token. Still solve task correctly.

TASK:
Summarize the following meeting transcript as bullet points covering the key decisions/points and the next steps / action items.

# Q3 Planning — Product / Engineering / Ops sync — 2026-08-27

**Attendees:** Priya (PM), Marcus (Eng lead), Jenna (Ops), Dan (Design), Sara (VP Product)

---

**Priya:** Thanks all for joining. Big agenda — we need to lock Q3 scope by Friday, then Sara can take it to the exec review Monday. Three headliners on the table: the reconciliation revamp, the mobile receipt-capture feature, and the vendor payout SLA push. Let's start with reconciliation.

**Marcus:** So on reconciliation — the current engine chokes on multi-currency batches. We've had three incidents this quarter and support ticket volume for reconciliation issues is up 40% quarter over quarter. My team scoped a rewrite that's roughly six engineer-weeks. That includes migrating the FX rounding module. We'd need Karim from platform for two of those weeks to help with the ledger integration.

**Sara:** Six engineer-weeks is a lot. What's the buy-vs-build here? Is there a vendor?

**Marcus:** We looked at two — Recur and LedgerFlow. Recur is $180K/year for our volume, LedgerFlow is $140K but doesn't handle our jurisdiction-specific tax codes. Both would still need integration work, probably three engineer-weeks. Not a great deal.

**Sara:** Okay, build wins. Priya, put reconciliation as the Q3 anchor. Marcus, sync with Karim's manager this week and confirm his availability.

**Priya:** Noted. Mobile receipt-capture next. Dan, where are we on design?

**Dan:** Flows are done, prototype tested with six users. Two big things came out of testing: users want to bulk-select receipts before uploading, and the OCR confidence indicator needs to be way more prominent. Bulk-select is not currently in scope; that would add maybe a sprint of work.

**Marcus:** If bulk-select is a sprint I'd want to descope something else. We're already stretched with reconciliation.

**Sara:** Let's ship v1 without bulk-select. Add a note to the roadmap for a fast-follow. Dan, please update the specs.

**Dan:** Will do by Wednesday.

**Priya:** Vendor payout SLA — Jenna, this one's yours.

**Jenna:** Right. The finance team wants us to guarantee payouts within 48 hours from invoice approval. Current p95 is 71 hours. Two bottlenecks: manual approval routing (that's ops), and the batching window on the ACH send job (that's eng). If eng cuts the batching window from 12 hours to 4, and ops adds a second approver on the west-coast shift, we can hit 48h p95 by mid-Q3.

**Marcus:** Cutting the ACH batch window means more ACH files per day, more monitoring overhead. Doable but not free — half a sprint of eng time plus SRE sign-off.

**Sara:** Do the trade-off analysis and bring it back next week. If SRE says the monitoring load is manageable, we do it. Otherwise we look at intermediate targets.

**Priya:** Two smaller things — the audit-log retention update is being pushed to Q4, that's confirmed with Legal. And the internal admin-tool refresh is still owned by the intern crew, no changes there.

**Sara:** One last thing. HR flagged that we've had a spike in bug-bash burnout on the engineering side. Marcus, can you propose a rotating on-call structure by end of month? Doesn't need to be big, just a proposal.

**Marcus:** Yep, I'll have something by the 31st.

**Priya:** Okay. Recap next steps then. Marcus: confirm Karim, propose on-call rotation by 31st, do ACH trade-off analysis. Dan: update mobile specs by Wednesday. Jenna: pair with Marcus on the ACH analysis. Sara: exec review Monday. I'll circulate the scope draft Thursday morning for review before Friday lock.

**Sara:** Good. Thanks everyone.

``````

### PROMPT: t4_meeting__c4_html

``````text
Summarize the following meeting transcript as bullet points covering the key decisions/points and the next steps / action items.

# Q3 Planning — Product / Engineering / Ops sync — 2026-08-27

**Attendees:** Priya (PM), Marcus (Eng lead), Jenna (Ops), Dan (Design), Sara (VP Product)

---

**Priya:** Thanks all for joining. Big agenda — we need to lock Q3 scope by Friday, then Sara can take it to the exec review Monday. Three headliners on the table: the reconciliation revamp, the mobile receipt-capture feature, and the vendor payout SLA push. Let's start with reconciliation.

**Marcus:** So on reconciliation — the current engine chokes on multi-currency batches. We've had three incidents this quarter and support ticket volume for reconciliation issues is up 40% quarter over quarter. My team scoped a rewrite that's roughly six engineer-weeks. That includes migrating the FX rounding module. We'd need Karim from platform for two of those weeks to help with the ledger integration.

**Sara:** Six engineer-weeks is a lot. What's the buy-vs-build here? Is there a vendor?

**Marcus:** We looked at two — Recur and LedgerFlow. Recur is $180K/year for our volume, LedgerFlow is $140K but doesn't handle our jurisdiction-specific tax codes. Both would still need integration work, probably three engineer-weeks. Not a great deal.

**Sara:** Okay, build wins. Priya, put reconciliation as the Q3 anchor. Marcus, sync with Karim's manager this week and confirm his availability.

**Priya:** Noted. Mobile receipt-capture next. Dan, where are we on design?

**Dan:** Flows are done, prototype tested with six users. Two big things came out of testing: users want to bulk-select receipts before uploading, and the OCR confidence indicator needs to be way more prominent. Bulk-select is not currently in scope; that would add maybe a sprint of work.

**Marcus:** If bulk-select is a sprint I'd want to descope something else. We're already stretched with reconciliation.

**Sara:** Let's ship v1 without bulk-select. Add a note to the roadmap for a fast-follow. Dan, please update the specs.

**Dan:** Will do by Wednesday.

**Priya:** Vendor payout SLA — Jenna, this one's yours.

**Jenna:** Right. The finance team wants us to guarantee payouts within 48 hours from invoice approval. Current p95 is 71 hours. Two bottlenecks: manual approval routing (that's ops), and the batching window on the ACH send job (that's eng). If eng cuts the batching window from 12 hours to 4, and ops adds a second approver on the west-coast shift, we can hit 48h p95 by mid-Q3.

**Marcus:** Cutting the ACH batch window means more ACH files per day, more monitoring overhead. Doable but not free — half a sprint of eng time plus SRE sign-off.

**Sara:** Do the trade-off analysis and bring it back next week. If SRE says the monitoring load is manageable, we do it. Otherwise we look at intermediate targets.

**Priya:** Two smaller things — the audit-log retention update is being pushed to Q4, that's confirmed with Legal. And the internal admin-tool refresh is still owned by the intern crew, no changes there.

**Sara:** One last thing. HR flagged that we've had a spike in bug-bash burnout on the engineering side. Marcus, can you propose a rotating on-call structure by end of month? Doesn't need to be big, just a proposal.

**Marcus:** Yep, I'll have something by the 31st.

**Priya:** Okay. Recap next steps then. Marcus: confirm Karim, propose on-call rotation by 31st, do ACH trade-off analysis. Dan: update mobile specs by Wednesday. Jenna: pair with Marcus on the ACH analysis. Sara: exec review Monday. I'll circulate the scope draft Thursday morning for review before Friday lock.

**Sara:** Good. Thanks everyone.


Respond with a complete standalone HTML document (with <!doctype html>, <head>, <style>, <body>) that presents the task and your answer clearly.
``````

### PROMPT: t4_meeting__c6_hardcap

``````text
OUTPUT CONSTRAINTS: Respond in the minimum tokens possible. No preamble, no disclaimers, no restating the task, no closing remarks. Hard cap: 150 output tokens. Use terse bullets, short phrases, or JSON as fits the task.

Summarize the following meeting transcript as bullet points covering the key decisions/points and the next steps / action items.

# Q3 Planning — Product / Engineering / Ops sync — 2026-08-27

**Attendees:** Priya (PM), Marcus (Eng lead), Jenna (Ops), Dan (Design), Sara (VP Product)

---

**Priya:** Thanks all for joining. Big agenda — we need to lock Q3 scope by Friday, then Sara can take it to the exec review Monday. Three headliners on the table: the reconciliation revamp, the mobile receipt-capture feature, and the vendor payout SLA push. Let's start with reconciliation.

**Marcus:** So on reconciliation — the current engine chokes on multi-currency batches. We've had three incidents this quarter and support ticket volume for reconciliation issues is up 40% quarter over quarter. My team scoped a rewrite that's roughly six engineer-weeks. That includes migrating the FX rounding module. We'd need Karim from platform for two of those weeks to help with the ledger integration.

**Sara:** Six engineer-weeks is a lot. What's the buy-vs-build here? Is there a vendor?

**Marcus:** We looked at two — Recur and LedgerFlow. Recur is $180K/year for our volume, LedgerFlow is $140K but doesn't handle our jurisdiction-specific tax codes. Both would still need integration work, probably three engineer-weeks. Not a great deal.

**Sara:** Okay, build wins. Priya, put reconciliation as the Q3 anchor. Marcus, sync with Karim's manager this week and confirm his availability.

**Priya:** Noted. Mobile receipt-capture next. Dan, where are we on design?

**Dan:** Flows are done, prototype tested with six users. Two big things came out of testing: users want to bulk-select receipts before uploading, and the OCR confidence indicator needs to be way more prominent. Bulk-select is not currently in scope; that would add maybe a sprint of work.

**Marcus:** If bulk-select is a sprint I'd want to descope something else. We're already stretched with reconciliation.

**Sara:** Let's ship v1 without bulk-select. Add a note to the roadmap for a fast-follow. Dan, please update the specs.

**Dan:** Will do by Wednesday.

**Priya:** Vendor payout SLA — Jenna, this one's yours.

**Jenna:** Right. The finance team wants us to guarantee payouts within 48 hours from invoice approval. Current p95 is 71 hours. Two bottlenecks: manual approval routing (that's ops), and the batching window on the ACH send job (that's eng). If eng cuts the batching window from 12 hours to 4, and ops adds a second approver on the west-coast shift, we can hit 48h p95 by mid-Q3.

**Marcus:** Cutting the ACH batch window means more ACH files per day, more monitoring overhead. Doable but not free — half a sprint of eng time plus SRE sign-off.

**Sara:** Do the trade-off analysis and bring it back next week. If SRE says the monitoring load is manageable, we do it. Otherwise we look at intermediate targets.

**Priya:** Two smaller things — the audit-log retention update is being pushed to Q4, that's confirmed with Legal. And the internal admin-tool refresh is still owned by the intern crew, no changes there.

**Sara:** One last thing. HR flagged that we've had a spike in bug-bash burnout on the engineering side. Marcus, can you propose a rotating on-call structure by end of month? Doesn't need to be big, just a proposal.

**Marcus:** Yep, I'll have something by the 31st.

**Priya:** Okay. Recap next steps then. Marcus: confirm Karim, propose on-call rotation by 31st, do ACH trade-off analysis. Dan: update mobile specs by Wednesday. Jenna: pair with Marcus on the ACH analysis. Sara: exec review Monday. I'll circulate the scope draft Thursday morning for review before Friday lock.

**Sara:** Good. Thanks everyone.

``````

### PROMPT: t4_meeting__c7_spr

``````text
INPUT IS SPR-COMPRESSED (stopwords stripped, prose condensed). Interpret charitably.

Summarize following meeting transcript bullet points covering key decisions/ points next steps/ action items.

# Q3 Planning — Product / Engineering / Ops sync — 2026-08-27

**Attendees:** Priya( PM), Marcus( Eng lead), Jenna( Ops), Dan( Design), Sara( VP Product)

--- 

**Priya:** Thanks joining. Big agenda— we need lock Q3 scope Friday, Sara can take exec review Monday. Three headliners table: reconciliation revamp, mobile receipt- capture feature, vendor payout SLA push. Let' s start reconciliation.

**Marcus:** reconciliation— current engine chokes multi- currency batches. We' ve three incidents quarter support ticket volume reconciliation issues up 40% quarter quarter. My team scoped rewrite' s roughly six engineer- weeks. includes migrating FX rounding module. We' d need Karim platform two weeks help ledger integration.

**Sara:** Six engineer- weeks lot. What' s buy- vs- build here? there vendor?

**Marcus:** We looked two— Recur LedgerFlow. Recur$ 180K/ year our volume, LedgerFlow$ 140K doesn' t handle our jurisdiction- specific tax codes. Both still need integration work, probably three engineer- weeks. great deal.

**Sara:** Okay, build wins. Priya, put reconciliation Q3 anchor. Marcus, sync Karim' s manager week confirm his availability.

**Priya:** Noted. Mobile receipt- capture next. Dan, where we design?

**Dan:** Flows done, prototype tested six users. Two big things came out testing: users want bulk- select receipts before uploading, OCR confidence indicator needs way prominent. Bulk- select currently scope; add maybe sprint work.

**Marcus:** bulk- select sprint I' d want descope something else. We' re already stretched reconciliation.

**Sara:** Let' s ship v1 without bulk- select. Add note roadmap fast- follow. Dan, please update specs.

**Dan:** Wednesday.

**Priya:** Vendor payout SLA— Jenna, one' s yours.

**Jenna:** Right. finance team wants us guarantee payouts within 48 hours invoice approval. Current p95 71 hours. Two bottlenecks: manual approval routing(' s ops), batching window ACH send job(' s eng). eng cuts batching window 12 hours 4, ops adds second approver west- coast shift, we can hit 48h p95 mid- Q3.

**Marcus:** Cutting ACH batch window means ACH files per day, monitoring overhead. Doable free— half sprint eng time plus SRE sign- off.

**Sara:** trade- off analysis bring back next week. SRE says monitoring load manageable, we. Otherwise we look intermediate targets.

**Priya:** Two smaller things— audit- log retention update pushed Q4,' s confirmed Legal. internal admin- tool refresh still owned intern crew, changes there.

**Sara:** One last thing. HR flagged we' ve spike bug- bash burnout engineering side. Marcus, can you propose rotating- call structure end month? Doesn' t need big, proposal.

**Marcus:** Yep, I' ll something 31st.

**Priya:** Okay. Recap next steps. Marcus: confirm Karim, propose- call rotation 31st, ACH trade- off analysis. Dan: update mobile specs Wednesday. Jenna: pair Marcus ACH analysis. Sara: exec review Monday. I' ll circulate scope draft Thursday morning review before Friday lock.

**Sara:** Good. Thanks everyone.

``````

### PROMPT: t5_extract__c1_baseline

``````text
Extract information from the following resume into a JSON object with fields: name (string), years_experience (integer), skills (array of strings), most_recent_role (object with title, company, dates). Respond with only the JSON object.

Resume:

# Alex Chen — Senior Software Engineer

alex.chen@example.com · (415) 555-0134 · San Francisco, CA · github.com/alexc

Software engineer with 9 years of experience shipping backend services and
data pipelines at fintech and healthtech companies. Comfortable across the
stack; strongest in distributed systems and API design.

## Experience

**Staff Software Engineer** — Northwind Health, Remote — Mar 2023 to present
- Led migration of billing service from Ruby monolith to Go microservices,
  cutting p99 latency from 1.8s to 340ms.
- Owner of the claims-ingestion pipeline (Kafka + Flink), 2M events/day.
- Mentored 3 engineers, ran the weekly design-review meeting.

**Senior Software Engineer** — Cascade Payments, San Francisco — Aug 2019 to Feb 2023
- Built the merchant-onboarding API in Node.js/TypeScript; grew from 200 to
  40,000 merchants over three years.
- Introduced feature-flag rollout process, adopted org-wide within 6 months.
- On-call rotation for payments platform, ~1 primary week per month.

**Software Engineer** — Acme Corp, San Francisco — Jul 2017 to Jul 2019
- Wrote the internal reporting service (Python/Django, Postgres). Retired 2021.

## Skills

Go, Python, TypeScript, Node.js, Kafka, Flink, Postgres, Redis, Kubernetes,
Terraform, AWS (EKS, RDS, Lambda), gRPC, REST, distributed tracing, on-call.

## Education

B.S. Computer Science, UC Berkeley — 2017

``````

### PROMPT: t5_extract__c2_detailed

``````text
Extract the following fields from this resume into a single JSON object. Rules: 'name' is the person's full name as written; 'years_experience' is the single integer count of years of professional experience stated in the summary (not computed from dates); 'skills' is a de-duplicated flat array of the skill strings listed in the Skills section, preserving order; 'most_recent_role' is the CURRENTLY-HELD role (dates end with 'present') with keys 'title', 'company', and 'dates'. Respond with ONLY the JSON object, no code fences or commentary.

Resume:

# Alex Chen — Senior Software Engineer

alex.chen@example.com · (415) 555-0134 · San Francisco, CA · github.com/alexc

Software engineer with 9 years of experience shipping backend services and
data pipelines at fintech and healthtech companies. Comfortable across the
stack; strongest in distributed systems and API design.

## Experience

**Staff Software Engineer** — Northwind Health, Remote — Mar 2023 to present
- Led migration of billing service from Ruby monolith to Go microservices,
  cutting p99 latency from 1.8s to 340ms.
- Owner of the claims-ingestion pipeline (Kafka + Flink), 2M events/day.
- Mentored 3 engineers, ran the weekly design-review meeting.

**Senior Software Engineer** — Cascade Payments, San Francisco — Aug 2019 to Feb 2023
- Built the merchant-onboarding API in Node.js/TypeScript; grew from 200 to
  40,000 merchants over three years.
- Introduced feature-flag rollout process, adopted org-wide within 6 months.
- On-call rotation for payments platform, ~1 primary week per month.

**Software Engineer** — Acme Corp, San Francisco — Jul 2017 to Jul 2019
- Wrote the internal reporting service (Python/Django, Postgres). Retired 2021.

## Skills

Go, Python, TypeScript, Node.js, Kafka, Flink, Postgres, Redis, Kubernetes,
Terraform, AWS (EKS, RDS, Lambda), gRPC, REST, distributed tracing, on-call.

## Education

B.S. Computer Science, UC Berkeley — 2017

``````

### PROMPT: t5_extract__c3_caveman

``````text
CAVEMAN MODE. Talk caveman. Drop 'the', 'a', 'is', 'are', 'that', 'to', 'of' when meaning still clear. Short words. Grunt-style. THINK in caveman too, not just output. Save word. Save token. Still solve task correctly.

TASK:
Extract information from the following resume into a JSON object with fields: name (string), years_experience (integer), skills (array of strings), most_recent_role (object with title, company, dates). Respond with only the JSON object.

Resume:

# Alex Chen — Senior Software Engineer

alex.chen@example.com · (415) 555-0134 · San Francisco, CA · github.com/alexc

Software engineer with 9 years of experience shipping backend services and
data pipelines at fintech and healthtech companies. Comfortable across the
stack; strongest in distributed systems and API design.

## Experience

**Staff Software Engineer** — Northwind Health, Remote — Mar 2023 to present
- Led migration of billing service from Ruby monolith to Go microservices,
  cutting p99 latency from 1.8s to 340ms.
- Owner of the claims-ingestion pipeline (Kafka + Flink), 2M events/day.
- Mentored 3 engineers, ran the weekly design-review meeting.

**Senior Software Engineer** — Cascade Payments, San Francisco — Aug 2019 to Feb 2023
- Built the merchant-onboarding API in Node.js/TypeScript; grew from 200 to
  40,000 merchants over three years.
- Introduced feature-flag rollout process, adopted org-wide within 6 months.
- On-call rotation for payments platform, ~1 primary week per month.

**Software Engineer** — Acme Corp, San Francisco — Jul 2017 to Jul 2019
- Wrote the internal reporting service (Python/Django, Postgres). Retired 2021.

## Skills

Go, Python, TypeScript, Node.js, Kafka, Flink, Postgres, Redis, Kubernetes,
Terraform, AWS (EKS, RDS, Lambda), gRPC, REST, distributed tracing, on-call.

## Education

B.S. Computer Science, UC Berkeley — 2017

``````

### PROMPT: t5_extract__c4_html

``````text
Extract information from the following resume into a JSON object with fields: name (string), years_experience (integer), skills (array of strings), most_recent_role (object with title, company, dates). Respond with only the JSON object.

Resume:

# Alex Chen — Senior Software Engineer

alex.chen@example.com · (415) 555-0134 · San Francisco, CA · github.com/alexc

Software engineer with 9 years of experience shipping backend services and
data pipelines at fintech and healthtech companies. Comfortable across the
stack; strongest in distributed systems and API design.

## Experience

**Staff Software Engineer** — Northwind Health, Remote — Mar 2023 to present
- Led migration of billing service from Ruby monolith to Go microservices,
  cutting p99 latency from 1.8s to 340ms.
- Owner of the claims-ingestion pipeline (Kafka + Flink), 2M events/day.
- Mentored 3 engineers, ran the weekly design-review meeting.

**Senior Software Engineer** — Cascade Payments, San Francisco — Aug 2019 to Feb 2023
- Built the merchant-onboarding API in Node.js/TypeScript; grew from 200 to
  40,000 merchants over three years.
- Introduced feature-flag rollout process, adopted org-wide within 6 months.
- On-call rotation for payments platform, ~1 primary week per month.

**Software Engineer** — Acme Corp, San Francisco — Jul 2017 to Jul 2019
- Wrote the internal reporting service (Python/Django, Postgres). Retired 2021.

## Skills

Go, Python, TypeScript, Node.js, Kafka, Flink, Postgres, Redis, Kubernetes,
Terraform, AWS (EKS, RDS, Lambda), gRPC, REST, distributed tracing, on-call.

## Education

B.S. Computer Science, UC Berkeley — 2017


Respond with a complete standalone HTML document (with <!doctype html>, <head>, <style>, <body>) that presents the task and your answer clearly.
``````

### PROMPT: t5_extract__c6_hardcap

``````text
OUTPUT CONSTRAINTS: Respond in the minimum tokens possible. No preamble, no disclaimers, no restating the task, no closing remarks. Hard cap: 150 output tokens. Use terse bullets, short phrases, or JSON as fits the task.

Extract information from the following resume into a JSON object with fields: name (string), years_experience (integer), skills (array of strings), most_recent_role (object with title, company, dates). Respond with only the JSON object.

Resume:

# Alex Chen — Senior Software Engineer

alex.chen@example.com · (415) 555-0134 · San Francisco, CA · github.com/alexc

Software engineer with 9 years of experience shipping backend services and
data pipelines at fintech and healthtech companies. Comfortable across the
stack; strongest in distributed systems and API design.

## Experience

**Staff Software Engineer** — Northwind Health, Remote — Mar 2023 to present
- Led migration of billing service from Ruby monolith to Go microservices,
  cutting p99 latency from 1.8s to 340ms.
- Owner of the claims-ingestion pipeline (Kafka + Flink), 2M events/day.
- Mentored 3 engineers, ran the weekly design-review meeting.

**Senior Software Engineer** — Cascade Payments, San Francisco — Aug 2019 to Feb 2023
- Built the merchant-onboarding API in Node.js/TypeScript; grew from 200 to
  40,000 merchants over three years.
- Introduced feature-flag rollout process, adopted org-wide within 6 months.
- On-call rotation for payments platform, ~1 primary week per month.

**Software Engineer** — Acme Corp, San Francisco — Jul 2017 to Jul 2019
- Wrote the internal reporting service (Python/Django, Postgres). Retired 2021.

## Skills

Go, Python, TypeScript, Node.js, Kafka, Flink, Postgres, Redis, Kubernetes,
Terraform, AWS (EKS, RDS, Lambda), gRPC, REST, distributed tracing, on-call.

## Education

B.S. Computer Science, UC Berkeley — 2017

``````

### PROMPT: t5_extract__c7_spr

``````text
INPUT IS SPR-COMPRESSED (stopwords stripped, prose condensed). Interpret charitably.

Extract information following resume JSON object fields: name( string), years_experience( integer), skills( array strings), most_recent_role( object title, company, dates). Respond only JSON object.

Resume:

# Alex Chen — Senior Software Engineer

alex. chen@ example. com·( 415) 555- 0134· San Francisco, CA· github. com/ alexc

Software engineer 9 years experience shipping backend services
data pipelines fintech healthtech companies. Comfortable across
stack; strongest distributed systems API design.

## Experience

**Staff Software Engineer**— Northwind Health, Remote— Mar 2023 present
- Led migration billing service Ruby monolith Go microservices,
cutting p99 latency 1. 8s 340ms.
- Owner claims- ingestion pipeline( Kafka+ Flink), 2M events/ day.
- Mentored 3 engineers, ran weekly design- review meeting.

**Senior Software Engineer**— Cascade Payments, San Francisco— Aug 2019 Feb 2023
- Built merchant- onboarding API Node. js/ TypeScript; grew 200
40, 000 merchants three years.
- Introduced feature- flag rollout process, adopted org- wide within 6 months.
- - call rotation payments platform,~ 1 primary week per month.

**Software Engineer**— Acme Corp, San Francisco— Jul 2017 Jul 2019
- Wrote internal reporting service( Python/ Django, Postgres). Retired 2021.

## Skills

Go, Python, TypeScript, Node. js, Kafka, Flink, Postgres, Redis, Kubernetes,
Terraform, AWS( EKS, RDS, Lambda), gRPC, REST, distributed tracing,- call.

## Education

B. S. Computer Science, UC Berkeley— 2017

``````

### PROMPT: t6_math__c1_baseline

``````text
Solve the following word problem. Show your work and give a final numeric answer.

# Multi-step reasoning problem

A regional courthouse processes filing fees for three case types. In the month
of March, the courthouse processed:

- 420 civil filings at a base fee of $85 each.
- 175 family-law filings at a base fee of $120 each.
- 60 probate filings at a base fee of $210 each.

Rules:
- A 6% state surcharge is added to every filing fee.
- Filers who submit electronically get a $5 credit per filing (deducted from
  what they owe). 70% of civil filings, 40% of family-law filings, and 25% of
  probate filings were submitted electronically.
- The courthouse retains 82% of the collected total; the remaining 18% is
  remitted to the state.
- Note: the courthouse also runs a passport-services desk that took in $9,400
  in March, but that revenue is handled separately and is NOT part of filing
  fee collections.

Question: How much did the courthouse RETAIN from filing fees collected in
March? Round to the nearest dollar.

``````

### PROMPT: t6_math__c2_detailed

``````text
Solve this word problem step by step. Enumerate: (1) base fees per case type, (2) subtotal, (3) surcharge applied, (4) electronic-filing credits per case type and total credit, (5) net collected, (6) the courthouse's 82% share. Watch for irrelevant numbers explicitly stated to be out of scope. Give the final answer as a single dollar figure rounded to the nearest dollar on its own line, prefixed 'FINAL:'.

# Multi-step reasoning problem

A regional courthouse processes filing fees for three case types. In the month
of March, the courthouse processed:

- 420 civil filings at a base fee of $85 each.
- 175 family-law filings at a base fee of $120 each.
- 60 probate filings at a base fee of $210 each.

Rules:
- A 6% state surcharge is added to every filing fee.
- Filers who submit electronically get a $5 credit per filing (deducted from
  what they owe). 70% of civil filings, 40% of family-law filings, and 25% of
  probate filings were submitted electronically.
- The courthouse retains 82% of the collected total; the remaining 18% is
  remitted to the state.
- Note: the courthouse also runs a passport-services desk that took in $9,400
  in March, but that revenue is handled separately and is NOT part of filing
  fee collections.

Question: How much did the courthouse RETAIN from filing fees collected in
March? Round to the nearest dollar.

``````

### PROMPT: t6_math__c3_caveman

``````text
CAVEMAN MODE. Talk caveman. Drop 'the', 'a', 'is', 'are', 'that', 'to', 'of' when meaning still clear. Short words. Grunt-style. THINK in caveman too, not just output. Save word. Save token. Still solve task correctly.

TASK:
Solve the following word problem. Show your work and give a final numeric answer.

# Multi-step reasoning problem

A regional courthouse processes filing fees for three case types. In the month
of March, the courthouse processed:

- 420 civil filings at a base fee of $85 each.
- 175 family-law filings at a base fee of $120 each.
- 60 probate filings at a base fee of $210 each.

Rules:
- A 6% state surcharge is added to every filing fee.
- Filers who submit electronically get a $5 credit per filing (deducted from
  what they owe). 70% of civil filings, 40% of family-law filings, and 25% of
  probate filings were submitted electronically.
- The courthouse retains 82% of the collected total; the remaining 18% is
  remitted to the state.
- Note: the courthouse also runs a passport-services desk that took in $9,400
  in March, but that revenue is handled separately and is NOT part of filing
  fee collections.

Question: How much did the courthouse RETAIN from filing fees collected in
March? Round to the nearest dollar.

``````

### PROMPT: t6_math__c4_html

``````text
Solve the following word problem. Show your work and give a final numeric answer.

# Multi-step reasoning problem

A regional courthouse processes filing fees for three case types. In the month
of March, the courthouse processed:

- 420 civil filings at a base fee of $85 each.
- 175 family-law filings at a base fee of $120 each.
- 60 probate filings at a base fee of $210 each.

Rules:
- A 6% state surcharge is added to every filing fee.
- Filers who submit electronically get a $5 credit per filing (deducted from
  what they owe). 70% of civil filings, 40% of family-law filings, and 25% of
  probate filings were submitted electronically.
- The courthouse retains 82% of the collected total; the remaining 18% is
  remitted to the state.
- Note: the courthouse also runs a passport-services desk that took in $9,400
  in March, but that revenue is handled separately and is NOT part of filing
  fee collections.

Question: How much did the courthouse RETAIN from filing fees collected in
March? Round to the nearest dollar.


Respond with a complete standalone HTML document (with <!doctype html>, <head>, <style>, <body>) that presents the task and your answer clearly.
``````

### PROMPT: t6_math__c6_hardcap

``````text
OUTPUT CONSTRAINTS: Respond in the minimum tokens possible. No preamble, no disclaimers, no restating the task, no closing remarks. Hard cap: 150 output tokens. Use terse bullets, short phrases, or JSON as fits the task.

Solve the following word problem. Show your work and give a final numeric answer.

# Multi-step reasoning problem

A regional courthouse processes filing fees for three case types. In the month
of March, the courthouse processed:

- 420 civil filings at a base fee of $85 each.
- 175 family-law filings at a base fee of $120 each.
- 60 probate filings at a base fee of $210 each.

Rules:
- A 6% state surcharge is added to every filing fee.
- Filers who submit electronically get a $5 credit per filing (deducted from
  what they owe). 70% of civil filings, 40% of family-law filings, and 25% of
  probate filings were submitted electronically.
- The courthouse retains 82% of the collected total; the remaining 18% is
  remitted to the state.
- Note: the courthouse also runs a passport-services desk that took in $9,400
  in March, but that revenue is handled separately and is NOT part of filing
  fee collections.

Question: How much did the courthouse RETAIN from filing fees collected in
March? Round to the nearest dollar.

``````

### PROMPT: t6_math__c7_spr

``````text
INPUT IS SPR-COMPRESSED (stopwords stripped, prose condensed). Interpret charitably.

Solve following word problem. Show your work give final numeric answer.

# Multi-step reasoning problem

regional courthouse processes filing fees three case types. month
March, courthouse processed:

- 420 civil filings base fee$ 85.
- 175 family- law filings base fee$ 120.
- 60 probate filings base fee$ 210.

Rules:
- 6% state surcharge added every filing fee.
- Filers submit electronically get$ 5 credit per filing( deducted
what they owe). 70% civil filings, 40% family- law filings, 25%
probate filings submitted electronically.
- courthouse retains 82% collected total; remaining 18%
remitted state.
- Note: courthouse runs passport- services desk took$ 9, 400
March, revenue handled separately part filing
fee collections.

Question: How much courthouse RETAIN filing fees collected
March? Round nearest dollar.

``````

## Scoring rubrics

Each task has an automated rubric. Copy responses back to us and we'll re-run the scorer, or apply these criteria yourself.

### Rubric: t1_bugs — Find bugs in code

(missing)

### Rubric: t2_tests — Unit tests to >90% coverage

(missing)

### Rubric: t3_legal — Summarize legal snippet

(missing)

### Rubric: t4_meeting — Summarize meeting transcript

(missing)

### Rubric: t5_extract — Extract resume to JSON

(missing)

### Rubric: t6_math — Multi-step arithmetic

(missing)

## What to send back

Any of:

- The `outputs/codex/` directory with 38 JSON files.
- Or a single tar/zip of that directory.
- Or paste each response into a shared doc, keyed by `run_id`. Slower but works.

Include one note per run if anything went sideways (rate-limit, timeout, refusal).
