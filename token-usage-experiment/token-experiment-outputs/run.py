import json, subprocess, sys, time
from pathlib import Path

MODEL = sys.argv[1] if len(sys.argv) > 1 else 'sonnet'
PROMPTS = Path('prompts')
OUT = Path(f'outputs/codex_{MODEL}')
OUT.mkdir(parents=True, exist_ok=True)

BASE_CMD = [
    'claude', '-p', '--output-format', 'json', '--model', MODEL,
    '--system-prompt', 'You are a helpful assistant.',
    '--strict-mcp-config', '--exclude-dynamic-system-prompt-sections',
    '--disallowed-tools', 'Bash', 'Read', 'Write', 'Edit', 'Glob', 'Grep',
    'WebFetch', 'WebSearch', 'Task', 'NotebookEdit', 'TodoWrite',
]

def call(prompt):
    t0 = time.time()
    r = subprocess.run(BASE_CMD, input=prompt, capture_output=True, text=True, timeout=600)
    dur = int((time.time() - t0) * 1000)
    if r.returncode != 0:
        return {'response': '', 'tokens': {'input': 0, 'output': 0, 'reasoning': 0},
                'duration_ms': dur, 'note': f'CLI exit {r.returncode}: {(r.stderr or "")[:400]}'}
    try:
        d = json.loads(r.stdout)
    except Exception as e:
        return {'response': r.stdout, 'tokens': {'input': 0, 'output': 0, 'reasoning': 0},
                'duration_ms': dur, 'note': f'unparsable JSON: {e}'}
    u = d.get('usage', {})
    inp = u.get('input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('cache_read_input_tokens', 0)
    out = {
        'response': d.get('result', ''),
        'tokens': {
            'input': inp,
            'output': u.get('output_tokens', 0),
            'reasoning': (u.get('output_tokens_details') or {}).get('thinking_tokens', 0),
        },
        'duration_ms': d.get('duration_ms', dur),
    }
    notes = []
    if d.get('is_error'): notes.append('is_error=true')
    if d.get('api_error_status'): notes.append(f"api_error_status={d['api_error_status']}")
    if d.get('stop_reason') not in (None, 'end_turn'): notes.append(f"stop_reason={d.get('stop_reason')}")
    if d.get('permission_denials'): notes.append(f"permission_denials={len(d['permission_denials'])}")
    if notes: out['note'] = '; '.join(notes)
    return out

files = sorted(PROMPTS.glob('*.txt'))
for i, pf in enumerate(files, 1):
    rid = pf.stem
    op = OUT / f'{rid}.json'
    if op.exists() and op.stat().st_size > 40:
        print(f'[{i}/{len(files)}] skip {rid}', flush=True); continue
    print(f'[{i}/{len(files)}] run  {rid}', flush=True)
    text = pf.read_text()
    for attempt in (1, 2):
        try:
            data = call(text); break
        except subprocess.TimeoutExpired:
            data = {'response': '', 'tokens': {'input': 0, 'output': 0, 'reasoning': 0},
                    'duration_ms': 600000, 'note': 'timeout after 600s'}
            if attempt == 1: continue
    data['run_id'] = rid
    data['model'] = MODEL
    data['prompt_chars'] = len(text)
    op.write_text(json.dumps(data, indent=2))
    print(f'    -> in={data["tokens"]["input"]} out={data["tokens"]["output"]} {data["duration_ms"]}ms {data.get("note","")}', flush=True)
print('done')
