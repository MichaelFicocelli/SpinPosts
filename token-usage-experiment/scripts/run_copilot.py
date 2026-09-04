#!/usr/bin/env python3
"""Run every applicable prompt through Copilot CLI (gpt-5.4).

For each run:
  1. Read the prompt file.
  2. Invoke `copilot --yolo -p <prompt> --model gpt-5.4 --usage-output-file <path>`.
  3. Strip the CLI's trailing session-summary footer.
  4. Write outputs/copilot/<run_id>.json with {"response": "..."} and
     outputs/copilot/<run_id>.usage.json with Copilot's own token counts.

Runs sequentially since Copilot enforces per-account concurrency limits.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
MANIFEST = json.loads((ROOT / "manifest.json").read_text())
OUT_DIR = ROOT / "outputs" / "copilot"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "gpt-5.4"


def strip_footer(text: str) -> str:
    """Remove Copilot's trailing summary block that follows the actual answer.

    The footer is a block of lines that includes "Changes", "Requests",
    "Tokens", "Resume". It is separated from the answer by one or more blank
    lines. Truncate at the first line whose left column matches those labels.
    """
    lines = text.splitlines()
    keep = []
    footer_re = re.compile(r"^(Changes|Requests|Tokens|Resume|Session|Model)\s")
    for ln in lines:
        if footer_re.match(ln):
            break
        keep.append(ln)
    while keep and keep[-1].strip() == "":
        keep.pop()
    return "\n".join(keep)


def run_one(prompt_file: Path, run_id: str) -> dict:
    out_path = OUT_DIR / f"{run_id}.json"
    usage_path = OUT_DIR / f"{run_id}.usage.json"
    if out_path.exists() and out_path.stat().st_size > 40:
        return {"run_id": run_id, "status": "cached"}

    prompt_text = prompt_file.read_text()
    result = subprocess.run(
        [
            "copilot", "--yolo",
            "-p", prompt_text,
            "--model", MODEL,
            "--usage-output-file", str(usage_path),
            "--log-level", "none",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    combined = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    response = strip_footer(combined)
    out_path.write_text(json.dumps({"response": response}))
    return {
        "run_id": run_id,
        "status": "ok" if result.returncode == 0 else "returncode-nonzero",
        "returncode": result.returncode,
        "response_chars": len(response),
    }


def main():
    if not shutil.which("copilot"):
        sys.exit("`copilot` CLI not on PATH")
    applicable = [e for e in MANIFEST if e["applicable"]]
    print(f"Running {len(applicable)} Copilot prompts (model={MODEL})")
    ok = 0
    for i, entry in enumerate(applicable, 1):
        pf = Path(entry["prompt_file"])
        try:
            r = run_one(pf, entry["run_id"])
        except subprocess.TimeoutExpired:
            r = {"run_id": entry["run_id"], "status": "timeout"}
            (OUT_DIR / f"{entry['run_id']}.json").write_text(json.dumps({"response": "[TIMEOUT]"}))
        except Exception as ex:
            r = {"run_id": entry["run_id"], "status": f"error: {ex}"}
        status = r.get("status", "?")
        rc = r.get("response_chars", "-")
        print(f"[{i:2}/{len(applicable)}] {entry['run_id']:32} {status:24} chars={rc}")
        if status in ("ok", "cached"):
            ok += 1
    print(f"\nCompleted: {ok}/{len(applicable)}")


if __name__ == "__main__":
    main()
