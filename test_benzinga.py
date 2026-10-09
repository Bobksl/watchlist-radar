import datetime as dt
import json
import urllib.error

import pytest
import benzinga
from page import render
from test_page_tradingview import snapshot

NOW = dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc)


def event(**changes):
    return {'id': 'one', 'security': {'symbol': 'MU'}, 'firm': 'Example',
            'date': '2026-10-08', 'updated': 1, 'analyst_insights': '<script>PRIVATE_BENZINGA</script>',
            'pt': '99999', **changes}


def test_identity_deduplication_freshness_and_target_withholding():
    payload = {'analyst-insights': [event(), event(updated=2),
               event(id='old', date='2026-07-16'), event(id='future', date='2026-10-10'),
               event(security={'symbol': 'AVGO'}), None]}
    items, rejected = benzinga.normalize(payload, 'MU', NOW.date())
    assert rejected == 2 and len(items) == 3
    assert {i['freshness'] for i in items} == {'recent_7d', 'historical', 'future_date_review'}
    assert next(i for i in items if i['id'] == 'one')['updated'] == 2
    assert all('pt' not in i and i['licence'] == 'unknown' for i in items)
    with pytest.raises(ValueError):
        benzinga.normalize({'analyst-insights': [event(security={'symbol': 'AVGO'})]}, 'MU', NOW.date())


def test_snapshot_history_hash_refusal_and_private_public_boundary(tmp_path_factory):
    folder = tmp_path_factory.mktemp('b')
    saved = benzinga.save('MU', {'analyst-insights': [event()]}, NOW, folder)
    path = folder / 'snapshots' / (saved['snapshot_sha256'] + '.json')
    original = path.read_bytes()
    benzinga.save('MU', {'analyst-insights': [event()]}, NOW + dt.timedelta(days=1), folder)
    assert path.read_bytes() == original
    benzinga.save('MU', {'analyst-insights': [event(updated=2)]}, NOW, folder)
    assert len(list((folder / 'snapshots').glob('*.json'))) == 2
    items = benzinga.load_private(folder, NOW.date())['items']
    assert items[0]['updated'] == 2
    evidence = {'benzinga': items}
    assert 'PRIVATE_BENZINGA' not in render(snapshot([]), research=evidence)
    local = render(snapshot([]), local=True, research=evidence)
    assert 'PRIVATE_BENZINGA' in local and '<script>PRIVATE_BENZINGA' not in local
    assert '99999' not in local
    latest = json.loads((folder / 'MU.json').read_text())
    (folder / 'MU.json').write_text(json.dumps({**latest, 'collected_utc': 1}))
    assert benzinga.load_private(folder)['unavailable'] == ['MU.json']
    (folder / 'MU.json').write_text(json.dumps(latest))
    (folder / 'snapshots' / (latest['snapshot_sha256'] + '.json')).write_bytes(b'{}')
    assert benzinga.load_private(folder)['unavailable'] == ['MU.json']


def test_failures_preserve_evidence_and_quota_stops_batch(tmp_path_factory, monkeypatch):
    folder = tmp_path_factory.mktemp('b')
    benzinga.save('MU', {'analyst-insights': [event()]}, NOW, folder)
    prior = (folder / 'MU.json').read_bytes()
    calls = []
    def fail(ticker, key):
        calls.append(ticker)
        raise urllib.error.HTTPError('https://example.invalid/?token=DO_NOT_LOG', 429, 'quota', {}, None)
    monkeypatch.setattr(benzinga, 'fetch', fail)
    result = benzinga.collect(['MU', 'AVGO'], 'DO_NOT_LOG', folder, NOW)
    assert result[0]['http_status'] == 429 and calls == ['MU']
    assert (folder / 'MU.json').read_bytes() == prior
    status = (folder / 'status.json').read_text()
    assert 'DO_NOT_LOG' not in status and json.loads(status)['not_attempted'] == ['AVGO']
    with pytest.raises(ValueError):
        benzinga.collect(['MU'], '', folder, NOW)


def test_input_and_response_limits():
    assert benzinga.symbols(['mu', 'MU']) == ['MU']
    for values in ([], ['../MU'], [f'A{i}' for i in range(41)]):
        with pytest.raises(ValueError):
            benzinga.symbols(values)
    for payload in ({}, [], {'analyst-insights': [event()] * 11}):
        with pytest.raises(ValueError):
            benzinga.normalize(payload, 'MU', NOW.date())


def test_cli_uses_watchlist_and_writes_private_preview(tmp_path_factory, monkeypatch):
    import sys
    root = tmp_path_factory.mktemp('b')
    monkeypatch.setattr(benzinga, 'ROOT', root)
    monkeypatch.setattr(benzinga, 'FOLDER', root / 'local/research/benzinga')
    monkeypatch.setenv('BENZINGA_API_KEY', 'TEST_SECRET')
    monkeypatch.setattr(sys, 'argv', ['benzinga.py'])
    monkeypatch.setattr(benzinga, 'fetch', lambda ticker, key: {'analyst-insights': [event()]})
    (root / 'watchlist.txt').write_text('MU MU')
    assert benzinga.main() == 0
    html = (root / 'local/benzinga.html').read_text(encoding='utf-8')
    assert 'PRIVATE_BENZINGA' in html and 'TEST_SECRET' not in html
    assert not (root / 'docs').exists()


def test_fetch_refuses_redirects_secret_echo_and_oversized_responses(monkeypatch):
    import io
    assert benzinga.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid') is None
    class Opener:
        def open(self, request, timeout):
            assert request.full_url.startswith('https://api.benzinga.com/api/v1/analyst/insights?')
            assert 'symbols=MU' in request.full_url and timeout == 20
            return io.BytesIO(raw)
    monkeypatch.setattr(benzinga.urllib.request, 'build_opener', lambda handler: Opener())
    for raw in (b'{"echo":"PRIVATEKEY"}', b'x' * 2_000_001):
        with pytest.raises(ValueError):
            benzinga.fetch('MU', 'PRIVATEKEY')
