#!/usr/bin/env python3
"""Inspect logs/dev/*.ndjson and try parse_5561 across offsets to find matches.
Usage: python3 scripts/inspect_bt50_logs.py [--max N] [--offsets M]
Writes a summary to logs/dev/inspect_report_YYYYMMDD_HHMMSS.json and prints a short table.
"""
import sys
from pathlib import Path
import json
import argparse
from collections import Counter
from datetime import datetime

repo = Path(__file__).resolve().parents[1]
logdir = repo / 'logs' / 'dev'

parser = argparse.ArgumentParser()
parser.add_argument('--max', type=int, default=200, help='Max bt50_raw entries to check')
parser.add_argument('--offsets', type=int, default=32, help='Offsets to try (0..N-1)')
args = parser.parse_args()

if not logdir.exists():
    print('No dev log directory:', logdir)
    sys.exit(1)

files = sorted(logdir.glob('dev_bridge_*.ndjson'), key=lambda p: p.stat().st_mtime)
if not files:
    print('No dev log files found in', logdir)
    sys.exit(1)

latest = files[-1]
print('Inspecting', latest)

# Add repo root for imports
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
count = 0
with latest.open() as f:
    for line in f:
        if count >= args.max:
            break
        try:
            j = json.loads(line)
        except Exception:
            continue
        if j.get('type') != 'bt50_raw':
            continue
        count += 1
        h = j.get('data', {}).get('hex')
        if not h:
            matches.append({'index': count, 'offset': None, 'samples': 0})
            continue
        b = bytes.fromhex(h)
        found = False
        if HAVE_PARSE:
            for off in range(0, args.offsets):
                try:
                    r = parse_5561(b[off:])
                except Exception:
                    r = None
                if r and r.get('samples'):
                    matches.append({'index': count, 'offset': off, 'samples': len(r.get('samples', [])), 'avg': (r.get('VX'), r.get('VY'), r.get('VZ'))})
                    found = True
                    break
        if not found:
            matches.append({'index': count, 'offset': None, 'samples': 0})

ctr = Counter([m['offset'] for m in matches])
summary = {
    'file': str(latest),
    'checked': count,
    'offset_counts': dict(ctr),
    'first_matches': matches[:20],
}

stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
outfile = logdir / f'inspect_report_{stamp}.json'
with outfile.open('w') as of:
    json.dump({'summary': summary, 'matches': matches}, of, indent=2)

print('Wrote', outfile)
print('Total bt50_raw checked:', count)
print('Offset counts (None = no match):')
for k, v in ctr.most_common():
    print(f'  {k}: {v}')

print('\nSample matches:')
for m in matches[:10]:
    print(m)

print('\nDone.')
