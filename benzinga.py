"""Bounded private Analyst Insights intake. Credentials come from BENZINGA_API_KEY."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
FOLDER = ROOT / 'local/research/benzinga'
PAGE_SIZE = 10


def symbols(values):
    tickers = list(dict.fromkeys(v.upper() for v in values))
    if not tickers or len(tickers) > 40 or any(not re.fullmatch(r'[A-Z][A-Z0-9.-]{0,9}', t) for t in tickers):
        raise ValueError('Supply 1 to 40 valid ticker symbols')
    return tickers


def normalize(payload, ticker, today):
    rows = payload.get('analyst-insights') if isinstance(payload, dict) else None
    if not isinstance(rows, list) or len(rows) > PAGE_SIZE:
        raise ValueError('Unexpected insights response')
    items, rejected = {}, 0
    for row in rows:
        try:
            if not isinstance(row, dict) or not isinstance(row.get('security'), dict) or row['security'].get('symbol') != ticker:
                raise ValueError('Ticker mismatch')
            event_date = dt.date.fromisoformat(row['date'])
            if not all(isinstance(row.get(k), str) and row[k].strip() for k in ('id', 'firm', 'analyst_insights')):
                raise ValueError('Missing event identity or text')
            updated = row.get('updated')
            if not isinstance(updated, int) or isinstance(updated, bool):
                raise ValueError('Missing revision timestamp')
            age = (today - event_date).days
            item = {'id': row['id'], 'ticker': ticker, 'date': row['date'],
                    'firm': row['firm'], 'updated': updated, 'text': row['analyst_insights'],
                    'action': str(row.get('action', '')), 'rating': str(row.get('rating', '')),
                    'freshness': 'future_date_review' if age < 0 else 'recent_7d' if age <= 7 else 'historical',
                    'licence': 'unknown', 'validation': 'unverified',
                    'target_status': 'withheld_pending_currency_split_and_source_checks'}
            if item['id'] not in items or updated > items[item['id']]['updated']:
                items[item['id']] = item
        except (ValueError, KeyError, TypeError):
            rejected += 1
    if rows and not items:
        raise ValueError('No valid requested-ticker insights')
    return sorted(items.values(), key=lambda x: (x['date'], x['updated']), reverse=True), rejected


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # The query-string credential must never follow a redirect.


def fetch(ticker, key):
    query = urllib.parse.urlencode({'symbols': ticker, 'pageSize': PAGE_SIZE,
                                   'sort': 'date:desc', 'token': key})
    request = urllib.request.Request('https://api.benzinga.com/api/v1/analyst/insights?' + query,
                                     headers={'Accept': 'application/json'})
    with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000 or key.encode() in raw:
        raise ValueError('Unsafe or oversized response')
    return json.loads(raw)


def save(ticker, payload, now, folder):
    from daily import atomic_write
    items, rejected = normalize(payload, ticker, now.date())
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode('utf-8')
    digest = hashlib.sha256(raw).hexdigest()
    path = folder / 'snapshots' / (digest + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as output:
            output.write(raw)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise ValueError('Snapshot integrity failure')
    record = {'schema': 'benzinga-private/1', 'ticker': ticker, 'collected_utc': now.isoformat(),
              'snapshot_sha256': digest, 'licence': 'unknown', 'validation': 'unverified',
              'coverage': 'latest page only; at most 10 insights, not exhaustive',
              'accepted': len(items), 'rejected': rejected}
    atomic_write(folder / f'{ticker}.json', json.dumps(record, indent=2))
    return record


def load_private(folder=None, today=None):
    folder = folder or FOLDER
    today = today or dt.datetime.now(dt.timezone.utc).date()
    items, unavailable = [], []
    for path in sorted(folder.glob('*.json')):
        if not re.fullmatch(r'[A-Z][A-Z0-9.-]{0,9}', path.stem):
            continue
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(record, dict) or not isinstance(record.get('collected_utc'), str):
                raise ValueError('Invalid collection metadata')
            dt.datetime.fromisoformat(record['collected_utc'])
            digest = record['snapshot_sha256']
            if record['schema'] != 'benzinga-private/1' or record['ticker'] != path.stem or not re.fullmatch('[a-f0-9]{64}', digest):
                raise ValueError('Invalid evidence pointer')
            raw = (folder / 'snapshots' / (digest + '.json')).read_bytes()
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError('Evidence hash mismatch')
            normalized, _ = normalize(json.loads(raw), path.stem, today)
            items += [{**x, 'collected_utc': record['collected_utc']} for x in normalized]
        except (ValueError, TypeError, KeyError, OSError):
            unavailable.append(path.name)
    return {'items': sorted(items, key=lambda x: (x['date'], x['updated']), reverse=True),
            'unavailable': unavailable}


def collect(tickers, key, folder=None, now=None):
    from daily import atomic_write
    tickers = symbols(tickers)
    if not key or key != key.strip():
        raise ValueError('Set BENZINGA_API_KEY before collection')
    folder = folder or FOLDER
    now = now or dt.datetime.now(dt.timezone.utc)
    statuses = []
    for ticker in tickers:
        try:
            saved = save(ticker, fetch(ticker, key), now, folder)
            statuses.append({'ticker': ticker, 'status': 'retrieved', 'accepted': saved['accepted'], 'rejected': saved['rejected']})
        except (OSError, ValueError, TypeError) as error:
            status = {'ticker': ticker, 'status': 'unavailable', 'error': type(error).__name__}
            if isinstance(error, urllib.error.HTTPError):
                status['http_status'] = error.code
            statuses.append(status)
            if status.get('http_status') in (401, 403, 429):
                break
    atomic_write(folder / 'status.json', json.dumps({'collected_utc': now.isoformat(),
                 'requested': tickers, 'not_attempted': tickers[len(statuses):], 'results': statuses}, indent=2))
    return statuses


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tickers', nargs='+', help='Defaults to watchlist.txt; maximum 40')
    args = parser.parse_args()
    try:
        result = collect(args.tickers or (ROOT / 'watchlist.txt').read_text(encoding='utf-8').split(),
                         os.environ.get('BENZINGA_API_KEY'))
    except (ValueError, OSError) as error:
        parser.exit(1, type(error).__name__ + ': collection not started; check credentials/watchlist\n')
    print(json.dumps(result))
    from daily import atomic_write
    from page import CSS, private_research_html
    evidence = load_private()
    preview = ROOT / 'local/benzinga.html'
    atomic_write(preview, '<!doctype html><html lang="en"><meta charset="utf-8">'
                 '<meta name="viewport" content="width=device-width,initial-scale=1">'
                 '<title>Private Benzinga intake</title><style>' + CSS + '</style><body><main>'
                 + private_research_html({'benzinga': evidence['items'], 'unavailable': evidence['unavailable']})
                 + '</main></body></html>')
    return int(any(x['status'] != 'retrieved' for x in result))


if __name__ == '__main__':
    raise SystemExit(main())
