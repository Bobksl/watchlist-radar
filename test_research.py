import json
import pytest
import research
import hashlib
from research import parse_report


def test_report_identity_and_private_unverified_provenance():
    raw = 'SDK log\n' + json.dumps({'code': 'US.MU', 'data': {'analyst_report_update_time_str': '2026-09-30'}})
    result = parse_report(raw, 'MU')
    assert result['licence'] == 'unknown' and result['validation'] == 'unverified'
    assert result['data']['analyst_report_update_time_str'] == '2026-09-30'
    with pytest.raises(ValueError):
        parse_report(raw, 'ASML')
    with pytest.raises(ValueError):
        parse_report('SDK error, no permission', 'MU')


def test_invalid_optional_private_evidence_cannot_stop_scan(tmp_path, monkeypatch):
    monkeypatch.setattr(research, 'ROOT', tmp_path)
    folder = tmp_path / 'local/research'
    folder.mkdir(parents=True)
    (folder / 'newsletter-evidence.json').write_text('{"items": [null]}')
    (folder / 'morningstar-MU.json').write_text('[]')
    result = research.load_private()
    assert result['reports'] == [] and result['newsletters'] == []
    assert len(result['unavailable']) == 4


def test_distinct_report_versions_remain_immutable_and_latest_is_updated(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp('r')
    first = {'ticker': 'MU', 'retrieved_utc': 'first', 'data': {'text': 'Original EUR 1.2'}, 'licence': 'unknown'}
    saved = research.archive_report(tmp_path, first)
    from pathlib import Path
    path = Path(saved['source_snapshot'])
    original = path.read_bytes()
    again = research.archive_report(tmp_path, {**first, 'retrieved_utc': 'later'})
    assert path.read_bytes() == original and again['source_snapshot'] == saved['source_snapshot']
    assert saved['source_snapshot_sha256'] == hashlib.sha256(original).hexdigest()
    revised = research.archive_report(tmp_path, {**first, 'data': {'text': 'Revised EUR 1.3'}})
    assert revised['source_snapshot'] != saved['source_snapshot'] and path.read_bytes() == original
    assert json.loads((tmp_path / 'morningstar-MU.json').read_text(encoding='utf-8')) == revised


@pytest.mark.parametrize('corrupt', ['{"ticker":"MU","data":{}}', '{}', '[]'])
def test_corrupt_snapshot_refused_without_replacing_latest(tmp_path_factory, corrupt):
    tmp_path = tmp_path_factory.mktemp('r')
    from pathlib import Path
    report = {'ticker': 'MU', 'data': {'text': 'original'}}
    saved = research.archive_report(tmp_path, report)
    latest = (tmp_path / 'morningstar-MU.json').read_bytes()
    Path(saved['source_snapshot']).write_text(corrupt)
    with pytest.raises(ValueError):
        research.archive_report(tmp_path, report)
    assert (tmp_path / 'morningstar-MU.json').read_bytes() == latest
