import json, glob, re, csv, sys
from pathlib import Path

T6_ANSWER = 58682  # 69300 -> x1.06 = 73458; credits 294*5+70*5+15*5 = 1895; net 71563; *0.82 = 58681.66

rows = []
for d in sorted(glob.glob('outputs/codex_*')):
    model = Path(d).name.replace('codex_', '')
    for f in sorted(glob.glob(f'{d}/*.json')):
        r = json.load(open(f))
        task, cond = r['run_id'].split('__')
        resp = r['response']
        t6ok = ''
        if task == 't6_math':
            nums = {int(n.replace(',', '').split('.')[0]) for n in re.findall(r'\d[\d,]*(?:\.\d+)?', resp)}
            t6ok = 'yes' if (T6_ANSWER in nums or T6_ANSWER + 1 in nums or T6_ANSWER - 1 in nums) else 'NO'
        rows.append({
            'model': model, 'task': task, 'condition': cond,
            'prompt_chars': r.get('prompt_chars', 0),
            'input_tokens': r['tokens']['input'],
            'output_tokens': r['tokens']['output'],
            'reasoning_tokens': r['tokens']['reasoning'],
            'response_chars': len(resp),
            'duration_ms': r['duration_ms'],
            't6_correct': t6ok,
            'note': r.get('note', ''),
        })

with open('summary.csv', 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

for model in sorted({r['model'] for r in rows}):
    mr = [r for r in rows if r['model'] == model]
    print(f'\n=== {model} ({len(mr)} runs) ===')
    print(f'{"condition":<14}{"n":>3}{"avg_in":>9}{"avg_out":>9}{"avg_reason":>11}{"avg_sec":>9}')
    for c in sorted({r['condition'] for r in mr}):
        cr = [r for r in mr if r['condition'] == c]
        n = len(cr)
        print(f'{c:<14}{n:>3}{sum(r["input_tokens"] for r in cr)/n:>9.0f}'
              f'{sum(r["output_tokens"] for r in cr)/n:>9.0f}'
              f'{sum(r["reasoning_tokens"] for r in cr)/n:>11.0f}'
              f'{sum(r["duration_ms"] for r in cr)/n/1000:>9.1f}')
    t6 = [r for r in mr if r['task'] == 't6_math']
    print('t6 math correct:', sum(1 for r in t6 if r['t6_correct'] == 'yes'), '/', len(t6),
          '| wrong:', [r['condition'] for r in t6 if r['t6_correct'] == 'NO'] or 'none')
