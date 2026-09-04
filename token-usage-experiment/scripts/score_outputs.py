#!/usr/bin/env python3
"""Score each output against the ground-truth rubric for its task.

Reads outputs/<model>/<run_id>.json for each (model, run) and produces
scored/results.json with per-run: response text, char counts, estimated
tokens (chars/4), and a success/partial/fail verdict with rationale.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
INPUTS = ROOT / "inputs"
PROMPTS = ROOT / "prompts"
OUTPUTS = ROOT / "outputs"
SCORED = ROOT / "scored"
SCORED.mkdir(exist_ok=True)

MODELS = ["opus", "sonnet", "fable", "copilot"]


def norm(s: str) -> str:
    return (s or "").lower()


# ----- Task 1 scoring: bug identification -----
def score_t1(response: str):
    r = norm(response)
    hits = 0
    details = []

    # Bug A: sort reverse=True (wrong order in group_transactions)
    bug_a = (
        ("reverse=true" in r or "reverse = true" in r or "newest first" in r or "descending" in r or "oldest first" in r or "sort order" in r)
        and ("group_transactions" in r or "sort" in r)
    )
    if bug_a:
        hits += 1
        details.append("A: sort order in group_transactions")

    # Bug B: average_daily_balance forward-fill (days without transactions)
    bug_b = (
        ("carry" in r or "forward" in r or "fill" in r or "propagat" in r or "last known" in r or "previous balance" in r or "get(day, 0)" in r or ".get(day,0)" in r or "zero for days" in r or "assumes zero" in r or "defaults to 0" in r)
        and ("average_daily_balance" in r or "balances_by_day" in r or "daily balance" in r or "day" in r)
    )
    if bug_b:
        hits += 1
        details.append("B: average_daily_balance missing forward-fill")

    # Bug C: top_accounts_by_activity missing reverse=True
    bug_c = (
        ("top_accounts" in r or "top accounts" in r or "top_n" in r or "top n" in r or "bottom" in r or "ascending" in r)
        and ("reverse" in r or "sort order" in r or "smallest" in r or "wrong order" in r or "bottom-n" in r or "bottom n" in r)
    )
    if bug_c:
        hits += 1
        details.append("C: top_accounts_by_activity missing reverse=True")

    if hits == 3:
        return "success", f"found all 3 bugs ({', '.join(details)})"
    if hits >= 1:
        return "partial", f"found {hits}/3 ({', '.join(details) or 'none named'})"
    return "fail", "found none of the 3 known bugs"


# ----- Task 2 scoring: unit test coverage -----
def score_t2(response: str):
    r = norm(response)
    hits = 0
    branches = []

    def has(*needles):
        return any(n in r for n in needles)

    # 1. balance <= 0
    if has("balance", "balance_cents") and has("zero", "<= 0", "<=0", "negative", "non-positive", "nonpositive", "0 cents", "0)"):
        # Loose: mentions zero/negative balance case
        if "zero" in r or "negative" in r or "<= 0" in r or "<=0" in r or "nonpositive" in r or "non-positive" in r:
            hits += 1
            branches.append("balance<=0")
    # 2. within grace period
    if has("grace", "10 day", "10-day", "ten day"):
        hits += 1
        branches.append("grace")
    # 3. just past grace, non-zero fee
    if has("past grace", "after grace", "beyond grace", "11 day", "12 day", "past due", "days_past_due"):
        hits += 1
        branches.append("past-grace")
    # 4. minimum fee floor
    if has("minimum", "min_fee", "min fee", "$5", "500 cent", "floor"):
        hits += 1
        branches.append("min-fee")
    # 5. maximum cap
    if has("maximum", "max_fee", "max fee", "cap", "25%", "0.25"):
        hits += 1
        branches.append("max-cap")
    # 6. weekend exclusion
    if has("weekend", "weekday", "saturday", "sunday", "monday-friday", "mon-fri", "friday to monday"):
        hits += 1
        branches.append("weekend")
    # 7. rounding
    if has("round", "half up", "half-up", "half_up", "cents rounding", "0.5"):
        hits += 1
        branches.append("rounding")
    # 8. today injection
    if has("today=", "today =", "today parameter", "inject", "custom today", "latefeecalculator(today", "latefeecalculator(today="):
        hits += 1
        branches.append("today-injection")

    if hits >= 7:
        return "success", f"covers {hits}/8 branches ({', '.join(branches)})"
    if hits >= 4:
        return "partial", f"covers {hits}/8 branches ({', '.join(branches)})"
    return "fail", f"covers only {hits}/8 branches ({', '.join(branches) or 'none'})"


# ----- Task 3 scoring: legal summary -----
LEGAL_KEY_POINTS = [
    ("mutual defend / indemnify each other for third-party claims from breach, negligence, IP infringement",
     [("indemnif", "defend"), ("breach", "warranty", "covenant", "misconduct", "infringe", "willful"), ("third", "third-party", "third party")]),
    ("IP carve-outs: modification, combination, out-of-scope use",
     [("modif", "combin", "outside", "out of scope", "scope"),]),
    ("prompt written notice; late notice only excused if materially prejudiced",
     [("notice", "notify"), ("prejudic", "materially")]),
    ("defending party controls defense/settlement but can't settle admitting fault without consent",
     [("defense", "defend", "control"), ("settle", "settlement", "consent", "admit")]),
    ("no indirect / consequential / lost profits damages (with exceptions)",
     [("indirect", "consequential", "punitive", "special", "incidental", "lost profits"),]),
    ("exceptions to cap: indemnity, confidentiality, gross negligence/willful misconduct, IP",
     [("exception", "except", "carve-out", "carve out", "does not apply", "not apply"), ("confidentia", "gross", "willful", "infring", "indemn")]),
    ("cap = greater of 12 months fees or $100,000",
     [("100,000", "$100,000", "100000", "one hundred thousand"), ("12", "twelve", "months")]),
]

LEGAL_KEY_TERMS = [
    ("indemnify", [("indemnif",), ("promise", "cover", "pay", "defend", "make whole", "reimburse", "compensate")]),
    ("third-party claim", [("third-party", "third party"), ("claim", "sue", "lawsuit")]),
    ("gross negligence / willful", [("gross", "willful", "reckless"), ("negligence", "misconduct", "care", "intentional", "on purpose")]),
    ("IP infringement / misappropriation", [("infringe", "misappropri"), ("intellectual property", "ip", "trade secret", "patent", "copyright")]),
    ("consequential / incidental / punitive", [("consequential", "incidental", "punitive", "special"), ("damage", "loss")]),
    ("cap on liability", [("cap", "limit", "maximum", "ceiling"), ("liab",)]),
    ("sole control of defense", [("sole", "control"), ("defense", "defend", "settle", "lawyer", "attorney")]),
    ("materially prejudiced", [("prejudic",), ("material", "significant", "harmed", "hurt")]),
]


def _matches_group(response: str, group):
    return all(any(needle in response for needle in tup) for tup in group)


def score_t3(response: str):
    r = norm(response)
    hits = 0
    covered = []
    for label, groups in LEGAL_KEY_POINTS:
        if _matches_group(r, groups):
            hits += 1
            covered.append(f"kp:{label[:35]}")
    for label, groups in LEGAL_KEY_TERMS:
        if _matches_group(r, groups):
            hits += 1
            covered.append(f"kt:{label}")
    if hits >= 12:
        return "success", f"covers {hits}/15 items"
    if hits >= 7:
        return "partial", f"covers {hits}/15 items"
    return "fail", f"covers {hits}/15 items"


# ----- Task 4 scoring: meeting summary -----
MEETING_ITEMS = [
    ("q3 lock by friday, exec review monday", [("friday",), ("monday", "exec")]),
    ("reconciliation anchor / build over vendor", [("reconcil",), ("build", "in-house", "vendor", "recur", "ledgerflow")]),
    ("mobile v1 without bulk-select", [("bulk", "bulk-select", "bulk select"), ("v1", "descope", "fast-follow", "fast follow", "later", "next")]),
    ("ocr confidence indicator more prominent", [("ocr",), ("confidence", "indicator", "prominent")]),
    ("ACH batch window 12h -> 4h; second west-coast approver; 48h p95 mid-Q3", [("ach", "batch"), ("48",)]),
    ("audit-log retention pushed to Q4", [("audit", "audit-log"), ("q4", "quarter", "retention", "pushed", "deferred")]),
    ("on-call rotation proposal for burnout", [("on-call", "oncall", "on call"), ("rotation", "burnout", "proposal", "proposed")]),
    ("Marcus confirm Karim", [("marcus",), ("karim", "confirm", "availability")]),
    ("Marcus on-call proposal by Aug 31", [("marcus",), ("31", "august 31", "aug 31", "end of month", "eom", "on-call", "oncall")]),
    ("Marcus ACH trade-off analysis", [("marcus",), ("ach", "trade-off", "tradeoff", "analysis")]),
    ("Dan update mobile specs by Wednesday", [("dan",), ("wednesday", "wed")]),
    ("Jenna pair with Marcus on ACH", [("jenna",), ("marcus", "ach", "pair")]),
    ("Sara to exec review Monday", [("sara",), ("monday", "exec", "review")]),
    ("Priya circulate scope draft Thursday", [("priya",), ("thursday", "thu", "scope", "draft", "circulate")]),
]


def score_t4(response: str):
    r = norm(response)
    hits = 0
    for label, groups in MEETING_ITEMS:
        if _matches_group(r, groups):
            hits += 1
    if hits >= 12:
        return "success", f"covers {hits}/14 items"
    if hits >= 7:
        return "partial", f"covers {hits}/14 items"
    return "fail", f"covers {hits}/14 items"


# ----- Task 5 scoring: structured extraction -----
def _extract_json(response: str):
    # Try each fenced json block first
    for m in re.finditer(r"```(?:json)?\s*(.*?)\s*```", response, re.DOTALL):
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    # Look for objects across the whole response (including HTML wrappers)
    # Find every '{' and try to match to a valid JSON object ending at some '}'
    for start in [i for i, ch in enumerate(response) if ch == "{"]:
        # scan for candidate ends (matching braces heuristically)
        depth = 0
        for i in range(start, len(response)):
            if response[i] == "{": depth += 1
            elif response[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(response[start : i + 1])
                        if isinstance(obj, dict) and ("name" in obj or "years_experience" in obj or "skills" in obj):
                            return obj
                    except Exception:
                        pass
                    break
    return None


T5_EXPECTED_SKILLS = {
    "go", "python", "typescript", "node.js", "nodejs", "node", "kafka", "flink",
    "postgres", "postgresql", "redis", "kubernetes", "k8s", "terraform", "aws",
    "grpc", "rest", "distributed tracing", "on-call", "oncall",
}


def score_t5(response: str):
    obj = _extract_json(response)
    if obj is None or not isinstance(obj, dict):
        return "fail", "response is not valid JSON"
    hits = 0
    checks = []

    if obj.get("name", "").strip() == "Alex Chen":
        hits += 1
        checks.append("name")

    yrs = obj.get("years_experience")
    if isinstance(yrs, int) and yrs == 9:
        hits += 1
        checks.append("years=9")
    elif isinstance(yrs, str) and yrs.strip() == "9":
        hits += 1
        checks.append("years=9(str)")

    skills = obj.get("skills")
    if isinstance(skills, list):
        seen = set(str(s).strip().lower() for s in skills)
        overlap = sum(1 for exp in T5_EXPECTED_SKILLS if exp in seen)
        if overlap >= 8:
            hits += 1
            checks.append(f"skills({overlap} known)")

    mr = obj.get("most_recent_role")
    if isinstance(mr, dict):
        if str(mr.get("title", "")).strip().lower() == "staff software engineer":
            hits += 1
            checks.append("title")
        if str(mr.get("company", "")).strip() == "Northwind Health":
            hits += 1
            checks.append("company")

    if hits == 5:
        return "success", f"all 5 fields correct ({', '.join(checks)})"
    if hits >= 3:
        return "partial", f"{hits}/5 fields correct ({', '.join(checks)})"
    return "fail", f"{hits}/5 fields correct ({', '.join(checks) or 'none'})"


# ----- Task 6 scoring: multi-step math -----
def score_t6(response: str):
    # Normalize LaTeX-style number formatting: \$, {,}, whitespace inside numbers
    text = response
    text = text.replace(r"\$", "$").replace(r"\,", "")
    text = re.sub(r"\{,\}", ",", text)   # LaTeX 58{,}682 -> 58,682
    text = re.sub(r"\\text\{[^}]*\}", "", text)  # \text{...} annotations
    # Then strip commas so 58,682 -> 58682
    flat = text.replace(",", "")
    candidates = re.findall(r"\$?\s*([0-9]+(?:\.[0-9]{1,2})?)", flat)
    nums = []
    for c in candidates:
        try:
            nums.append(float(c))
        except ValueError:
            pass
    # Prefer any number close to the right answer (or the passport-included fail-mode)
    target = 58682
    near = [n for n in nums if abs(n - target) <= 50 or abs(n - (target + 9400)) <= 50]
    if near:
        near.sort(key=lambda x: abs(x - target))
        return _score_num(near[0])
    return "fail", f"no answer near ${target} found"


def _score_num(v: float):
    if abs(v - 58682) <= 5:
        return "success", f"answer ${v:.0f} within $5 of $58,682"
    if abs(v - 58682) <= 50:
        return "partial", f"answer ${v:.0f} within $50 of $58,682"
    if abs(v - 68082) <= 50:  # included passport revenue by mistake
        return "fail", f"answer ${v:.0f} — included the $9,400 passport revenue distractor"
    return "fail", f"answer ${v:.0f} not close to $58,682"


SCORERS = {
    "t1_bugs": score_t1,
    "t2_tests": score_t2,
    "t3_legal": score_t3,
    "t4_meeting": score_t4,
    "t5_extract": score_t5,
    "t6_math": score_t6,
}


def main():
    manifest = json.loads((ROOT / "manifest.json").read_text())
    results = []
    missing = []

    for entry in manifest:
        if not entry["applicable"]:
            continue
        prompt_text = Path(entry["prompt_file"]).read_text()
        prompt_chars = len(prompt_text)
        prompt_tokens = round(prompt_chars / 4)

        for model in MODELS:
            out_path = OUTPUTS / model / f"{entry['run_id']}.json"
            row = {
                "run_id": entry["run_id"],
                "task_id": entry["task_id"],
                "task_label": entry["task_label"],
                "condition_id": entry["condition_id"],
                "condition_label": entry["condition_label"],
                "model": model,
                "prompt_chars": prompt_chars,
                "prompt_tokens_est": prompt_tokens,
            }
            if not out_path.exists():
                row["status"] = "missing"
                row["response"] = ""
                row["response_chars"] = 0
                row["response_tokens_est"] = 0
                row["total_tokens_est"] = prompt_tokens
                row["verdict"] = "fail"
                row["rationale"] = "output file missing"
                missing.append(row["run_id"] + "/" + model)
                results.append(row)
                continue
            try:
                data = json.loads(out_path.read_text())
                response = data.get("response", "")
            except Exception as e:
                row["status"] = "error"
                row["response"] = ""
                row["response_chars"] = 0
                row["response_tokens_est"] = 0
                row["total_tokens_est"] = prompt_tokens
                row["verdict"] = "fail"
                row["rationale"] = f"invalid output json: {e}"
                results.append(row)
                continue

            resp_chars = len(response)
            resp_tokens = round(resp_chars / 4)
            row["status"] = "ok"
            row["response"] = response
            row["response_chars"] = resp_chars
            row["response_tokens_est"] = resp_tokens
            row["total_tokens_est"] = prompt_tokens + resp_tokens

            verdict, rationale = SCORERS[entry["task_id"]](response)
            row["verdict"] = verdict
            row["rationale"] = rationale
            results.append(row)

    (SCORED / "results.json").write_text(json.dumps(results, indent=2))
    summary = {
        "total": len(results),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "missing": sum(1 for r in results if r["status"] == "missing"),
        "success": sum(1 for r in results if r["verdict"] == "success"),
        "partial": sum(1 for r in results if r["verdict"] == "partial"),
        "fail": sum(1 for r in results if r["verdict"] == "fail"),
        "missing_ids": missing,
    }
    (SCORED / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
