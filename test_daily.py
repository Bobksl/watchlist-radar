import datetime as dt
import json

import pytest

import radar
import daily


def test_review_requires_real_booleans_and_unique_indices():
    items = [{"tags": ["deal"], "title": "deal"}]
    with pytest.raises(ValueError):
        radar.apply_review(items, {"items": [{"i": 0, "about_company": "false", "material": True}]})


def test_unavailable_opend_never_constructs_quote_context(monkeypatch):
    import socket
    import sys
    from types import SimpleNamespace
    def unavailable(address, timeout):
        assert address == ("127.0.0.1", 11111) and timeout == 3
        raise ConnectionRefusedError("offline")
    monkeypatch.setattr(socket, "create_connection", unavailable)
    monkeypatch.setitem(sys.modules, "moomoo", SimpleNamespace(
        RET_OK=0, OpenQuoteContext=lambda **kwargs: pytest.fail("OpenD constructor must not run")))
    with pytest.raises(RuntimeError, match="OpenD unavailable"):
        radar.load_universe(["MU"])


def test_unlabelled_claim_is_private():
    from test_radar import card
    c = card()
    del c["checks"][0]["claims"][0]["source"]["licence"]
    assert radar.redact_card(c)["checks"][0]["claims"] == []


def test_broken_optional_card_does_not_abort(tmp_path):
    (tmp_path / "MU.json").write_text("{broken")
    cards, refused = radar.load_cards({"MU"}, tmp_path)
    assert cards == {} and refused


def test_sessions_dst_holidays_and_early_close():
    assert len(daily.session_dates(dt.date(2026, 7, 3), 5)) == 5
    assert daily.session_bounds(dt.date(2026, 7, 3)) is None
    assert daily.session_bounds(dt.date(2026, 11, 27))[1].hour == 18  # 13 ET
    assert not daily.due(dt.datetime(2026, 11, 27, 18, tzinfo=dt.timezone.utc), {})
    assert daily.due(dt.datetime(2026, 3, 6, 15, tzinfo=dt.timezone.utc), {})
    assert not daily.due(dt.datetime(2026, 3, 9, 13, 59, tzinfo=dt.timezone.utc), {})
    assert daily.due(dt.datetime(2026, 3, 9, 14, tzinfo=dt.timezone.utc), {})
    assert not daily.due(dt.datetime(2026, 3, 9, 14, tzinfo=dt.timezone.utc), {"attempt_session": "2026-03-09"})


def test_failure_retains_page_and_bounded_publish_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(daily, "ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.html").write_text("last good")
    (tmp_path / "watchlist.txt").write_text("MU")
    now = dt.datetime(2026, 3, 9, 14, tzinfo=dt.timezone.utc)
    def broken(wl):
        raise RuntimeError("private file data")
    assert daily.refresh(now, publish=False, scan=broken) == "failed"
    assert (tmp_path / "docs" / "index.html").read_text() == "last good"
    public = (tmp_path / "docs" / "status.json").read_text()
    assert "private file data" not in public and '"scan": "failed"' in public
    calls = []
    def failed_push(*args, **kwargs):
        calls.append(args)
        raise RuntimeError("offline")
    monkeypatch.setattr(radar, "publish", failed_push)
    assert daily.refresh(now, force=True, scan=lambda wl: "20260309_1000") == "publication_failed"
    for i in range(4):
        outcome = daily.refresh(now, scan=lambda wl: pytest.fail("must not collect twice"))
        assert outcome == ("publication_failed" if i < 2 else "not_due")
    assert len(calls) == 3


def test_os_lock_prevents_overlap(tmp_path):
    with daily.scan_lock(tmp_path / "lock"):
        with pytest.raises(OSError):
            with daily.scan_lock(tmp_path / "lock"):
                pytest.fail("overlap")
    with daily.scan_lock(tmp_path / "lock"):
        pass


def test_offline_scan_mixed_coverage_and_render_failure_retention(tmp_path, monkeypatch):
    import pandas as pd
    import page
    from test_radar import frame
    monkeypatch.setattr(radar, "HERE", tmp_path)
    uni = pd.DataFrame({"ticker": ["A", "B", "C"], "watchlist": [True, True, False],
                        "name": ["A", "B", "C"], "last_price": [100., 100., 100.],
                        "chg": [0., 0., 0.], "volume_ratio": [1., 1., 1.], "mcap": [3e9]*3,
                        "update_time": ["2026-10-08 10:00"]*3}).set_index("ticker")
    bars = frame(list(range(100, 230)), "2026-01-01")
    bars["raw_close"] = bars["close"] * 2  # synthetic adjustment factor
    monkeypatch.setattr(radar, "load_universe", lambda wl: uni)
    monkeypatch.setattr(radar, "load_bars", lambda *a: ({t: bars for t in uni.index}, bars.close))
    monkeypatch.setattr(radar, "vcp_setups", lambda *a: pd.DataFrame(columns=["actionable"]))
    monkeypatch.setattr(radar, "earnings_calendar", lambda *a: pd.DataFrame(columns=["ticker", "date", "when", "eps_forecast", "n_est"]))
    monkeypatch.setattr(radar, "load_cards", lambda *a: ({}, []))
    monkeypatch.setattr(radar, "load_key", lambda: None)
    stats = radar.bar_stats
    monkeypatch.setattr(radar, "bar_stats", lambda f: {**stats(f), "bb_pct": 0.5})
    monkeypatch.setattr(radar.time, "sleep", lambda *a: None)
    def news(name, *a):
        if name == "A":
            raise RuntimeError("offline fixture")
        return []
    monkeypatch.setattr(radar, "fetch_news", news)
    stamp = radar.run(["A", "B"])
    result = json.loads((tmp_path / "runs" / f"{stamp}.json").read_text())
    rows = {r["ticker"]: r for r in result["rows"]}
    assert rows["A"]["coverage"]["news"] == "error"
    assert rows["B"]["coverage"]["news"] == "success_empty"
    assert rows["C"]["coverage"]["news"] == "skipped_not_flagged"
    assert rows["A"]["hi20"] == bars.high.iloc[-20:].max() * 2
    good = (tmp_path / "docs" / "index.html").read_text(encoding="utf-8")
    monkeypatch.setattr(page, "render", lambda *a, **k: (_ for _ in ()).throw(ValueError("bad render")))
    with pytest.raises(ValueError):
        radar.run(["A", "B"], with_news=False)
    assert (tmp_path / "docs" / "index.html").read_text(encoding="utf-8") == good


def test_public_commit_excludes_unrelated_staged_changes(tmp_path, monkeypatch):
    import subprocess
    repo, remote = tmp_path / "repo", tmp_path / "remote"
    repo.mkdir()
    def git(*a):
        return subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
    git("init", "-b", "main")
    git("config", "user.name", "test")
    git("config", "user.email", "test@example.invalid")
    git("init", "--bare", str(remote))
    git("remote", "add", "origin", str(remote))
    (repo / "unrelated.txt").write_text("original")
    git("add", ".")
    git("commit", "-m", "initial")
    git("update-ref", "refs/remotes/origin/main", git("rev-parse", "HEAD"))
    real_run = subprocess.run
    def offline_remote(cmd, **kwargs):
        if cmd[:2] in (["git", "fetch"], ["git", "push"]):
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[:2] == ["git", "ls-remote"]:
            head = real_run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
            return subprocess.CompletedProcess(cmd, 0, head + "\trefs/heads/main", "")
        return real_run(cmd, **kwargs)
    monkeypatch.setattr(subprocess, "run", offline_remote)
    (repo / "unrelated.txt").write_text("private change")
    git("add", "unrelated.txt")
    (repo / "docs").mkdir()
    (repo / "docs" / "status.json").write_text('{"scan":"failed"}')
    monkeypatch.setattr(radar, "HERE", repo)
    radar.publish(None, include_status=True)
    assert git("show", "HEAD:unrelated.txt") == "original"
    assert git("diff", "--cached", "--name-only") == "unrelated.txt"
    assert git("rev-parse", "HEAD") == git("ls-remote", "origin", "refs/heads/main").split()[0]
