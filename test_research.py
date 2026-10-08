import json
import pytest
import research
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
