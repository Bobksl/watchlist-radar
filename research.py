"""Private Morningstar acquisition pilot; no report content enters docs/ or runs/."""
import datetime as dt
import json
import hashlib
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PILOT = ('MU', 'AVGO', 'ASML')
SCRIPT = Path.home() / '.claude/skills/moomooapi/scripts/quote/get_research_morningstar_report.py'


def load_private():
    """Optional local evidence never prevents publication of the market scan."""
    result = {'newsletters': [], 'reports': [], 'unavailable': []}
    paths = [('newsletters', ROOT / 'local/research/newsletter-evidence.json')]
    paths += [('reports', ROOT / f'local/research/morningstar-{t}.json') for t in PILOT]
    for kind, path in paths:
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
            if kind == 'newsletters':
                if not isinstance(record['items'], list) or any(not isinstance(x, dict)
                        or not isinstance(x.get('claims', []), list) for x in record['items']):
                    raise ValueError('Invalid newsletter evidence')
                result[kind] = record['items'][:30]
            else:
                if (not isinstance(record, dict) or record.get('ticker') not in PILOT
                        or path.name != f'morningstar-{record["ticker"]}.json'
                        or not isinstance(record.get('data'), dict)
                        or not isinstance(record.get('retrieved_utc'), str)
                        or not isinstance(record['data'].get('analyst_report_by_line', []), list)):
                    raise ValueError('Invalid report evidence')
                result[kind].append(record)
        except (OSError, ValueError, KeyError, TypeError):
            result['unavailable'].append(path.name)
    return result


def parse_report(stdout, ticker):
    for line in stdout.splitlines():
        if line.startswith('{'):
            report = json.loads(line)
            if report.get('code') != 'US.' + ticker or not isinstance(report.get('data'), dict):
                raise ValueError('Report identity mismatch')
            return {'ticker': ticker, 'publisher': 'Morningstar', 'licence': 'unknown',
                    'retrieved_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                    'validation': 'unverified', 'data': report['data']}
    raise ValueError('No research result')


def archive_report(target, report):
    """Keep the first retrieval of each distinct normalized payload, then update latest."""
    from daily import atomic_write
    payload = json.dumps(report['data'], ensure_ascii=False, sort_keys=True).encode('utf-8')
    data_hash = hashlib.sha256(payload).hexdigest()
    snapshot = target / 'snapshots' / f'morningstar-{report["ticker"]}-{data_hash}.json'
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps({**report, 'data_sha256': data_hash}, ensure_ascii=False, indent=2)
    try:
        with snapshot.open('x', encoding='utf-8', newline='\n') as source:
            source.write(content)
    except FileExistsError:
        saved = json.loads(snapshot.read_text(encoding='utf-8'))
        if (not isinstance(saved, dict) or saved.get('ticker') != report['ticker']
                or saved.get('data') != report['data']):
            raise ValueError('Existing snapshot integrity failure')
    record = {**report, 'data_sha256': data_hash,
              'source_snapshot': str(snapshot.resolve()),
              'source_snapshot_sha256': hashlib.sha256(snapshot.read_bytes()).hexdigest(),
              'hash_scope': 'normalized SDK payload; not publisher authenticity'}
    atomic_write(target / f'morningstar-{report["ticker"]}.json', json.dumps(record, ensure_ascii=False, indent=2))
    return record


def collect():
    from daily import atomic_write
    target = ROOT / 'local/research'
    target.mkdir(parents=True, exist_ok=True)
    results = []
    for ticker in PILOT:
        try:
            response = subprocess.run([sys.executable, '-B', str(SCRIPT), '--json', 'US.' + ticker],
                                      creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                                      capture_output=True, text=True, encoding='utf-8', timeout=30, check=True)
            report = parse_report(response.stdout, ticker)
            archive_report(target, report)
            results.append({'ticker': ticker, 'status': 'retrieved',
                            'report_date': report['data'].get('analyst_report_update_time_str')})
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            results.append({'ticker': ticker, 'status': 'unavailable', 'error': type(exc).__name__})
    atomic_write(target / 'morningstar-status.json', json.dumps(results, indent=2))
    print(json.dumps(results))


if __name__ == '__main__':
    collect()
