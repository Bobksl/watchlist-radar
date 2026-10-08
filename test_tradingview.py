from urllib.parse import parse_qs, urlparse

import pytest
from pathlib import Path

import tradingview as tv


def test_verified_chart_and_export_report_unmapped():
    query = parse_qs(urlparse(tv.chart_url("ASML", "D")).query)
    assert query == {"symbol": ["NASDAQ:ASML"], "interval": ["D"]}
    assert tv.chart_url("AAPL", "15")
    assert tv.chart_url("MU") is None
    assert tv.chart_url('AAPL&symbol=BAD') is None
    with pytest.raises(ValueError):
        tv.chart_url("AAPL", "<script>")
    assert tv.export_symbols(["ASML", "MU", "AAPL", "ASML"]) == (
        "NASDAQ:ASML,NASDAQ:AAPL", ["MU"]
    )


def test_parser_sections_duplicates_and_unverified_prefix():
    assert tv.parse_watchlist("###Tech,NASDAQ:AAPL,NASDAQ:MU\nMSFT AAPL") == [
        "AAPL", "MU", "MSFT"
    ]
    assert tv.chart_url("MU") is None
    assert tv.parse_watchlist("NYSE:ORCL,AMEX:SPY") == ["ORCL", "SPY"]
    assert tv.chart_url("ORCL") is None


@pytest.mark.parametrize("text", [
    "NASDAQ:AAPL,NYSE:AAPL", "NYSE:AAPL", "HKEX:700", "AAPL<script>",
    "NASDAQ:", "", "###Only a section", "AAPL,,MSFT", "AAPL,",
])
def test_parser_rejects_invalid_or_conflicting_input(text):
    with pytest.raises(ValueError):
        tv.parse_watchlist(text)


def test_import_preview_backup_and_failed_validation(tmp_path):
    target = tmp_path / "watchlist.txt"
    target.write_text("ORCL MU\n", encoding="utf-8")
    source = tmp_path / "export.txt"
    source.write_text("NASDAQ:AAPL,NASDAQ:MU", encoding="utf-8")
    tickers, backup = tv.import_watchlist(source, target)
    assert tickers == ["AAPL", "MU"] and backup is None
    assert target.read_text() == "ORCL MU\n"
    _, backup = tv.import_watchlist(source, target, write=True)
    assert backup.read_text() == "ORCL MU\n"
    assert target.read_text() == "AAPL MU\n"
    source.write_text("NASDAQ:AAPL,NYSE:AAPL", encoding="utf-8")
    with pytest.raises(ValueError):
        tv.import_watchlist(source, target, write=True)
    assert target.read_text() == "AAPL MU\n"
    assert len(list((tmp_path / "local").glob("watchlist-*.txt"))) == 1


def test_atomic_replace_failure_preserves_original_and_backup(tmp_path, monkeypatch):
    source, target = tmp_path / "source.txt", tmp_path / "watchlist.txt"
    source.write_text("AAPL")
    original = b"MU\r\n"
    target.write_bytes(original)

    def fail_replace(self, destination):
        raise OSError("synthetic replacement failure")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="synthetic"):
        tv.import_watchlist(source, target, write=True)
    assert target.read_bytes() == original
    assert next((tmp_path / "local").glob("watchlist-*.txt")).read_bytes() == original
    assert not list(tmp_path.glob("*.pending"))
