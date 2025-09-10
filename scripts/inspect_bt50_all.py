#!/usr/bin/env python3
"""Inspect all logs/dev/*.ndjson, pick the file with most bt50_raw entries, and try parse_5561 across offsets to find matches.
Writes a report to logs/dev/inspect_all_report_YYYYMMDD_HHMMSS.json and prints a short summary.
"""
import sys
from pathlib import Path
import json
from collections import Counter
from datetime import datetime

repo = Path(__file__).resolve().parents[1]
logdir = repo / 'logs' / 'dev'

if not logdir.exists():
    print('No dev log dir:', logdir)
    sys.exit(1)

files = list(logdir.glob('dev_bridge_*.ndjson'))
if not files:
    print('No dev logs')
    sys.exit(1)

# Count bt50_raw per file
counts = {}
for f in files:
    c = 0
    with f.open() as fh:
        for ln in fh:
            if '"type": "bt50_raw"' in ln:
                c += 1
    counts[f] = c

best = max(counts.items(), key=lambda kv: kv[1])[0]
print('Selected file:', best)
print('bt50_raw count:', counts[best])

# Import parser
if str(repo) not in sys.path:
    sys.path.insert(0, str(repo))
try:
    from src.impact_bridge.ble.wtvb_parse import parse_5561
    HAVE_PARSE = True
except Exception as e:
    print('Could not import parse_5561:', e)
    parse_5561 = None
    HAVE_PARSE = False

matches = []
max_check = 500
with best.open() as fh:
    idx = 0
    for ln in fh:
        if idx >= max_check:
            break
        if '"type": "bt50_raw"' not in ln:
            continue
        idx += 1
        try:
            j = json.loads(ln)
        except Exception:
            continue
        h = j.get('data', {}).get('hex')
        if not h:
            matches.append({'index': idx, 'offset': None, 'samples': 0})
            continue
        b = bytes.fromhex(h)
        found = False
        if HAVE_PARSE:
            for off in range(0, 64):
                try:
                    r = parse_5561(b[off:])
                except Exception:
                    r = None
                if r and r.get('samples'):
                    matches.append({'index': idx, 'offset': off, 'samples': len(r.get('samples', [])), 'avg': (r.get('VX'), r.get('VY'), r.get('VZ'))})
                    found = True
                    break
        if not found:
            matches.append({'index': idx, 'offset': None, 'samples': 0})

ctr = Counter([m['offset'] for m in matches])
summary = {'file': str(best), 'bt50_raw_total': counts[best], 'checked': len(matches), 'offset_counts': dict(ctr)}

stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
outfile = logdir / f'inspect_all_report_{stamp}.json'
with outfile.open('w') as of:
    json.dump({'summary': summary, 'matches': matches[:200]}, of, indent=2)

print('Wrote', outfile)
print('Summary:', summary)
