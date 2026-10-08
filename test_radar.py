"""Checks for the radar's own logic (no network):  C:\\Python314\\python.exe -m pytest -q test_radar.py"""
import datetime as dt

import numpy as np
import pandas as pd

import json

from page import render
from radar import (CARD_SCHEMA, SQUEEZE_PCT, WEIGHTS, apply_review, bar_stats, load_cards, peer_events,
                   reaction_returns, redact_card, score, scoreboard, tag_title)


def card(licence="licensed", schema=CARD_SCHEMA):
    claim = {"id": "c-1", "subject": "FQ3 revenue", "verdict": "confirmed", "reason": "within interval",
             "claimed": {"value": "41456000000", "unit": "USD", "per_share": False}, "evidence": [],
             "measurements": [{"name": "gap_pct", "value": "4.17", "unit": "%"}],
             "source": {"kind": "broker_note", "publisher": "UBS", "date": "2026-09-23",
                        "link": "local:ubs.pdf", "locator": "p.5", "licence": licence}}
    checks = [{"check": 1, "name": "historical_facts", "status": "pass", "claims": [claim], "measurements": []}]
    checks += [{"check": n, "name": name, "status": "not_supplied", "claims": [], "measurements": []}
               for n, name in [(2, "target_arithmetic"), (3, "implied_assumptions"), (4, "guidance_record"),
                               (5, "target_distribution")]]
    return {"schema": schema, "spec": "v2.2", "ticker": "MU", "cik": "723125", "as_of": "2026-10-01",
            "facts_as_of": "2026-06-25", "price": None, "checks": checks}


def test_licensed_values_never_reach_the_public_page():
    public = redact_card(card())
    assert public["checks"][0]["claims"] == [] and public["checks"][0]["licensed_counts"] == {"confirmed": 1}
    run = {"rows": [], "picks": [], "weights": WEIGHTS, "squeeze_pct": SQUEEZE_PCT, "generated_hkt": "",
           "generated_et": "", "quote_time": "", "bar_date": "", "universe": 0, "with_history": 0}
    pub = render({**run, "cards": {"MU": public}})
    loc = render({**run, "cards": {"MU": card()}}, local=True)
    assert "$41.46bn" not in pub and "1 confirmed" in pub
    assert "$41.46bn" in loc and "gap pct 4.17%" in loc
    assert redact_card(card(licence="public"))["checks"][0]["claims"]        # public sources publish in full


def test_cards_with_unknown_schema_are_refused(tmp_path):
    (tmp_path / "MU.json").write_text(json.dumps(card()), encoding="utf-8")
    (tmp_path / "NVDA.json").write_text(json.dumps({**card(schema="street-validator/2"), "ticker": "NVDA"}))
    (tmp_path / "AAPL.json").write_text(json.dumps({**card(), "ticker": "AAPL"}))       # not in universe
    cards, refused = load_cards({"MU", "NVDA"}, tmp_path)
    assert list(cards) == ["MU"] and refused == ["NVDA.json (street-validator/2)"]


def test_failed_leg_floor_earns_no_vcp_points():
    base = {"vcp_status": "Coiling, 3% to pivot", "vcp_setup": "coiling", "vcp_legs": 2, "vcp_tier": "proto",
            "vcp_pivot": 50.0}
    assert score({**base, "vcp_leg_floor": False})[2] == []
    assert score({**base, "vcp_leg_floor": True})[2] == ["vcp"]
    assert score({**base, "vcp_leg_floor": None})[2] == ["vcp"]        # forming coil: not testable


def test_llm_review_drops_off_topic_and_keeps_unreviewed():
    items = [{"title": "TTEC Digital Earns Microsoft Partner Award", "tags": ["deal"]},
             {"title": "Microsoft Raises Cloud Guidance", "tags": ["results"]},
             {"title": "Microsoft Signs AI Supply Deal", "tags": ["deal"]}]
    out = {"items": [{"i": 0, "about_company": False, "material": True, "tags": ["deal"], "why": "x"},
                     {"i": 1, "about_company": True, "material": True, "tags": ["results", "bogus"],
                      "why": "Guide raised"}],
           "summary": "Cloud guidance raised."}
    reviewed, summary = apply_review(items, out)
    assert reviewed[0]["tags"] == []                                # supplier's award, not Microsoft news
    assert reviewed[1]["tags"] == ["results"] and reviewed[1]["why"] == "Guide raised"   # unknown tag dropped
    assert reviewed[2]["tags"] == ["deal"] and "checked" not in reviewed[2]             # model skipped it
    assert summary == "Cloud guidance raised."


def frame(closes, start="2026-09-21"):
    idx = pd.bdate_range(start, periods=len(closes))
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 1e6,
                         "raw_close": c})


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
    s = bar_stats(frame(np.r_[wild, calm], start="2025-06-02"))
    assert s["bb_pct"] <= SQUEEZE_PCT
    assert s["lo20"] <= s["bar_close"] <= s["hi20"] and s["atr14"] > 0
    calm_then_wild = np.r_[100 * np.exp(np.cumsum(rng.normal(0, 0.002, 200))), wild[:30] / wild[0] * 100]
    loose = bar_stats(frame(calm_then_wild, start="2025-06-02"))
    assert loose["bb_pct"] > SQUEEZE_PCT


def test_score_points_reasons_and_flags():
    row = {"earnings_date": "2026-09-30", "earnings_when": "after close", "implied_move": 0.076,
           "past_abs": 0.069, "past_up": 9, "past_n": 22, "bb_pct": 0.5, "chg": 0.124, "volume_ratio": 3.3,
           "last_vol_x": 1.0, "last_ret": 0.0, "watchlist": True,
           "news": [{"tags": ["rating"]}, {"tags": []}]}
    pts, why, flags = score(row)
    assert pts == WEIGHTS["earnings"] + WEIGHTS["news"] + WEIGHTS["mover"] + WEIGHTS["watchlist"]
    assert flags == ["earnings", "news", "mover"]
    assert any("±7.6%" in w for w in why) and any("+12.4%" in w for w in why)
    quiet = score({"last_vol_x": 2.5, "last_ret": 0.0})       # a flat day still counts as quiet
    assert quiet[0] == WEIGHTS["quiet_volume"]


def test_peer_read_through():
    ev = peer_events({"MU", "SNDK", "WDC", "NVDA"}, {"MU": "2026-09-30 after close"})
    assert ev["SNDK"].startswith("MU (memory) reports 2026-09-30")
    assert "MU" not in ev and "NVDA" not in ev                # the reporter itself and other themes


def test_scoreboard_measures_from_run_price():
    # Run on Mon 21 Sep at price 100; A then closes 110 on Tue (next session), B and C barely move.
    frames = {"A": frame([100, 110, 110, 110, 110, 121]), "B": frame([100, 101, 101, 101, 101, 101]),
              "C": frame([100, 99, 99, 99, 99, 99])}
    past = {"generated_et": "2026-09-21 12:28", "picks": ["A"], "rows": [
        {"ticker": "A", "last_price": 100.0, "chg": 0.0, "volume_ratio": 1.0, "flags": ["mover"]},
        {"ticker": "B", "last_price": 100.0, "flags": []}, {"ticker": "C", "last_price": 100.0, "flags": []}]}
    board = scoreboard([past], frames)
    pick = board["picks"][0]
    assert pick["ticker"] == "A" and np.isclose(pick["ret_1"], 0.10) and np.isclose(pick["ret_5"], 0.21)
    mover = next(f for f in board["flags"] if f["flag"] == "mover")
    assert np.isclose(mover["ratio_1"], 0.10 / 0.01) and mover["n_1"] == 1   # typical |move| is 1%
    legacy = {**past, "rows": [{k: v for k, v in r.items() if k != 'flags'} for r in past['rows']]}
    assert scoreboard([legacy], frames)['picks'][0]['flags'] == ['legacy_unknown']
    fresh = {"generated_et": "2026-09-28 12:00", "picks": ["A"], "rows": [{"ticker": "A", "last_price": 1.0}]}
    assert scoreboard([fresh], frames) == {"picks": [], "flags": []}      # no completed session yet
