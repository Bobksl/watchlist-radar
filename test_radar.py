"""Checks for the radar's own logic (no network):  C:\\Python314\\python.exe -m pytest -q test_radar.py"""
import datetime as dt

import numpy as np
import pandas as pd

from radar import SQUEEZE_PCT, WEIGHTS, reaction_returns, score, squeeze_stats, tag_title


def frame(closes, start="2026-09-21"):
    idx = pd.bdate_range(start, periods=len(closes))
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 1e6})


def test_reaction_day_depends_on_report_time():
    f = frame([100, 110, 121, 133.1])                      # Mon..Thu, +10% a day
    after = pd.Timestamp("2026-09-22 16:05")               # Tue after close -> Tue close to Wed close
    before = pd.Timestamp("2026-09-22 07:00")              # Tue before open -> Mon close to Tue close
    weekend = pd.Timestamp("2026-09-20 16:00")             # Sunday -> Fri (missing) base: skipped
    today = dt.date(2026, 9, 30)
    assert np.allclose(reaction_returns(f, [after], today), [0.10])
    assert np.allclose(reaction_returns(f, [before], today), [0.10])
    assert reaction_returns(f, [weekend], today) == []
    assert reaction_returns(f, [pd.Timestamp("2026-09-30 16:00")], today) == []   # not reported yet


def test_news_tags_and_noise():
    assert tag_title("Jefferies Raises Price Target on Bloom Energy to $264") == ["rating"]
    assert "m&a" in tag_title("AMD to Acquire Startup in $2 Billion Deal")
    assert tag_title("BE INVESTOR DEADLINE APPROACHING: Faruqi & Faruqi Reminds Investors") == []
    assert tag_title("Oracle Options Spot-On: 400K Contracts Traded") == []
    assert tag_title("Nvidia shares edge higher") == []
    assert tag_title("Netlist Seeks Exclusion Order at ITC") == []
    assert tag_title("Today's Ratings for Micron, With a Forecast Between $1,200 to $1,540") == ["rating"]


def test_squeeze_flags_tight_recent_range():
    rng = np.random.default_rng(0)
    wild = 100 * np.exp(np.cumsum(rng.normal(0, 0.03, 200)))
    calm = wild[-1] * np.exp(np.cumsum(rng.normal(0, 0.002, 30)))
    s = squeeze_stats(frame(np.r_[wild, calm], start="2025-06-02"))
    assert s["bb_pct"] <= SQUEEZE_PCT
    calm_then_wild = np.r_[100 * np.exp(np.cumsum(rng.normal(0, 0.002, 200))), wild[:30] / wild[0] * 100]
    loose = squeeze_stats(frame(calm_then_wild, start="2025-06-02"))
    assert loose["bb_pct"] > SQUEEZE_PCT


def test_score_points_and_reasons():
    row = {"earnings_date": "2026-09-30", "earnings_when": "after close", "implied_move": 0.076,
           "past_abs": 0.069, "past_up": 9, "past_n": 22, "bb_pct": 0.5, "chg": 0.124, "volume_ratio": 3.3,
           "last_vol_x": 1.0, "last_ret": 0.0, "watchlist": True,
           "news": [{"tags": ["rating"]}, {"tags": []}]}
    pts, why = score(row)
    assert pts == WEIGHTS["earnings"] + WEIGHTS["news"] + WEIGHTS["mover"] + WEIGHTS["watchlist"]
    assert any("±7.6%" in w for w in why) and any("+12.4%" in w for w in why)
    quiet = score({"last_vol_x": 2.5, "last_ret": 0.0})       # a flat day still counts as quiet
    assert quiet[0] == WEIGHTS["quiet_volume"]
