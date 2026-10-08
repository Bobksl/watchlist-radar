from page import render
from radar import WEIGHTS, SQUEEZE_PCT


def snapshot(tickers):
    return {"rows": [{"ticker": t, "last_price": 100, "points": 3, "why": [],
                       "watchlist": True, "mcap": 1} for t in tickers], "picks": tickers,
            "weights": WEIGHTS, "squeeze_pct": SQUEEZE_PCT, "generated_hkt": "",
            "generated_et": "", "quote_time": "", "bar_date": "", "universe": len(tickers),
            "with_history": 0}


def test_verified_chart_links_and_range_guidance():
    html = render(snapshot(["AAPL"]))
    assert "symbol=NASDAQ%3AAAPL" in html
    assert "interval=D" in html and "interval=15" in html
    assert 'aria-label="AAPL daily chart on TradingView"' in html
    assert "YTD" in html and "date range" in html
    assert 'id="tv-shortlist"' in html and "NASDAQ:AAPL" in html


def test_unmapped_symbols_stay_visible_and_are_not_guessed():
    html = render(snapshot(["AAPL", "UNKNOWN"]))
    assert "Chart mapping unavailable" in html
    assert "Unmapped: UNKNOWN" in html
    assert "NASDAQ%3AUNKNOWN" not in html


def test_free_plan_controls_and_empty_export():
    html = render(snapshot([]))
    assert "Free-plan chart handoff" in html
    assert 'id="tv-copy" disabled' in html
    assert 'id="tv-interval"' in html
    assert "not an account sync" in html
