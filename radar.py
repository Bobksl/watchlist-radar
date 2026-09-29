"""Watchlist radar: tech, semiconductor and AI-adjacent names likely to move in the next few sessions.

Run with moomoo OpenD open and logged in on 127.0.0.1:11111:

    C:\\Python314\\python.exe radar.py              # writes runs/<stamp>.json and docs/index.html
    C:\\Python314\\python.exe radar.py --no-news    # skip the news API
    C:\\Python314\\python.exe radar.py --publish    # also commit and push the page to GitHub Pages

Four flags feed the ranking: earnings in the next few sessions, a VCP coil (the Admiralty detector,
called unchanged), a volatility squeeze, and material news in the last 48 hours. Today's move and
yesterday's volume are shown as context. Every run is saved in runs/ so the flags can be scored
against what happened next. A research aid for choosing what to look at; not investment advice.

Sources: moomoo OpenD (universe, live quotes), Yahoo Finance via yfinance (daily bars, past
earnings dates, options), Nasdaq earnings calendar, moomoo news search.
"""
import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

HERE = Path(__file__).resolve().parent
VCP_ROOT = Path(r"C:\Users\user\Admiralty Harbour Capital Limited\Admiralty Harbour Capital Ltd - portfolio_analysis_new"
                r"\portfolio_analysis\src\backtest\strategies\rule_based")
NY, HK = ZoneInfo("America/New_York"), ZoneInfo("Asia/Hong_Kong")

# moomoo US industry plates: core tech, then AI-adjacent power, build-out and data-centre groups.
PLATES = {
    "US.LIST2015": "Semiconductors", "US.LIST2016": "Semi Equipment & Materials",
    "US.LIST2072": "Electronic Components", "US.LIST2098": "Communication Equipment",
    "US.LIST2492": "Computer Hardware", "US.LIST2075": "Consumer Electronics",
    "US.LIST2508": "Software - Infrastructure", "US.LIST2470": "Software - Application",
    "US.LIST2004": "Internet Content", "US.LIST2252": "IT Services",
    "US.LIST2493": "Electrical Equipment", "US.LIST2462": "Independent Power",
    "US.LIST2461": "Renewable Utilities", "US.LIST2430": "Uranium",
    "US.LIST2033": "Engineering & Construction", "US.LIST2463": "Industrial Machinery",
    "US.LIST2482": "Specialty REITs",
}
MIN_MCAP, MIN_PRICE = 2e9, 5.0     # universe floor; watchlist names always pass
EARNINGS_SESSIONS = 5              # today plus the next few sessions
NEWS_HOURS = 48
SQUEEZE_PCT = 0.02                 # Bollinger width in the narrowest 2% of its last 126 sessions
TOP_PICKS = 5
# ponytail: hand-set additive weights; v2 replaces them with each flag's measured move uplift
WEIGHTS = {"earnings": 3, "vcp_actionable": 3, "vcp": 1.5, "squeeze": 2, "news": 2, "news_multi": 1,
           "mover": 1, "quiet_volume": 1, "watchlist": 1}

NEWS_URL = "https://ai-news-search.moomoo.com/news_search"
NEWS_TAGS = {
    "rating": r"upgrade|downgrade|initiat|price target|target price|ratings?\b|overweight|underweight"
              r"|outperform|underperform",
    "results": r"earnings|results|guidance|outlook|revenue|profit|\beps\b|quarterly|beats?\b|miss(es)?\b",
    "deal": r"contract|deal\b|agreement|partner|orders? (for|from|worth)|supply|customer|collaborat|launch"
            r"|unveil",
    "m&a": r"acqui|merger|buyout|takeover|stake|spin.?off|divest",
    "capital": r"offering|convertible|buyback|repurchase|dividend|split|notes due|raises? \$",
    "risk": r"lawsuit|legal proceeding|infring|patent|probe|investigat|\bsec\b|\bdoj\b|short.seller|short report|recall|antitrust|export"
            r"|ban\b|tariff|subpoena|delay",
}
NEWS_NOISE = re.compile(r"investor deadline|class action|law firm|shareholder alert|reminds investors"
                        r"|options spot-on|unusual options|stocks that explain|top gainers|top losers"
                        r"|biggest movers|market moves|stocks to watch|premarket movers", re.I)


def load_universe(watchlist):
    """OpenD: plate members plus the watchlist, with a live snapshot for each."""
    from moomoo import OpenQuoteContext, RET_OK
    q = OpenQuoteContext(host="127.0.0.1", port=11111)
    try:
        members = []
        for i, (code, plate) in enumerate(PLATES.items()):
            if i:
                time.sleep(3.1)  # get_plate_stock allows 10 calls per 30 s
            ret, df = q.get_plate_stock(code)
            if ret != RET_OK:
                raise RuntimeError(f"OpenD plate {plate}: {df}")
            members.append(df[["code"]].assign(plate=plate))
        uni = pd.concat(members).drop_duplicates("code")
        extra = [f"US.{t}" for t in watchlist if f"US.{t}" not in set(uni.code)]
        uni = pd.concat([uni, pd.DataFrame({"code": extra, "plate": "Watchlist"})])
        snaps, codes = [], uni.code.tolist()
        for i in range(0, len(codes), 400):  # snapshot takes at most 400 codes per call
            ret, s = q.get_market_snapshot(codes[i:i + 400])
            if ret != RET_OK:
                raise RuntimeError(f"OpenD snapshot: {s}")
            snaps.append(s)
    finally:
        q.close()
    s = pd.concat(snaps).merge(uni, on="code")
    s["ticker"] = s.code.str[3:]
    s["watchlist"] = s.ticker.isin(watchlist)
    s = s[s.watchlist | ((s.total_market_val >= MIN_MCAP) & (s.last_price >= MIN_PRICE))].copy()
    s["chg"] = s.last_price / s.prev_close_price - 1
    s["off_high"] = s.last_price / s.highest52weeks_price - 1
    keep = ["ticker", "name", "plate", "watchlist", "last_price", "chg", "volume_ratio", "turnover",
            "total_market_val", "off_high", "update_time"]
    return s[keep].rename(columns={"total_market_val": "mcap"}).set_index("ticker")


def yahoo(ticker):
    return ticker.replace(".", "-")


def load_bars(tickers, now_ny):
    """Two years of completed daily bars per ticker, in the frame shape the VCP detector expects."""
    sys.path.insert(0, str(VCP_ROOT))
    from vcp.data.helpers import extract_yfinance_frame
    symbols = [yahoo(t) for t in tickers] + ["SPY"]
    raw = yf.download(symbols, period="2y", interval="1d", auto_adjust=False, group_by="ticker",
                      progress=False, threads=True)
    session_done = now_ny.time() >= dt.time(16, 15)
    frames = {}
    for t in tickers + ["SPY"]:
        f = extract_yfinance_frame(raw, yahoo(t))
        if f.empty:
            continue
        if not session_done:  # today's bar is still forming; flags use completed bars only
            f = f[f.index.date < now_ny.date()]
        if len(f) >= 60:
            frames[t] = f
    return frames, frames.pop("SPY")["close"]


def vcp_setups(frames, spy):
    """Admiralty US scanner primitives, unchanged: forming coils plus confirmed bases still coiling."""
    sys.path.insert(0, str(VCP_ROOT))
    from vcp.live import scanner_core as sc
    from vcp.live.us_scanner import USScannerConfig
    cfg = USScannerConfig()
    feats = sc.compute_features(frames, spy, cfg, raw_price_feature="raw_close_usd")
    survivors, _ = sc.history_tradability_liquidity_filter(
        feats, cfg, market="US", raw_price_feature="raw_close_usd", turnover_usd_feature="med_turnover_20d",
        max_tick_cost_bps=cfg.max_tick_cost_bps, turnover_floor_usd=cfg.min_median_turnover_usd)
    forming = sc.run_forming_detection(survivors, frames, spy, cfg)
    confirmed = sc.run_detection(survivors, frames, spy, cfg)
    status = sc.classify_confirmed(confirmed, frames, cfg)
    rows = ([dict(r, setup_type="forming") for r in forming]
            + [dict(r, setup_type="coiling") for r, s in zip(confirmed, status) if s == "coiling"])
    cols = ["ticker", "setup_type", "n_contractions", "tier", "actionable", "status", "resistance",
            "last_low", "pct_below_pivot", "vol_dryup_ratio", "atr_ratio", "stage2", "score"]
    if not rows:
        return pd.DataFrame(columns=cols).set_index("ticker")
    rep = sc.rank_pattern_candidates(pd.DataFrame(rows), cfg)
    rep["stage2"] = rep.ticker.map(sc.stage2_mask(feats, cfg)).fillna(False)
    rep = rep.sort_values(["actionable", "score"], ascending=False).drop_duplicates("ticker")
    return rep[cols].set_index("ticker")


def squeeze_stats(frame):
    """Bollinger width percentile over 6 months, narrowest-range-of-7, and yesterday's volume vs 50 days."""
    c = frame["close"]
    width = 4 * c.rolling(20).std() / c.rolling(20).mean()
    recent = width.iloc[-126:].dropna()
    bb_pct = float((recent <= recent.iloc[-1]).mean()) if len(recent) >= 60 else np.nan
    rng = frame["high"] - frame["low"]
    nr7 = bool(rng.iloc[-1] <= rng.iloc[-7:].min())
    vol_x = float(frame["volume"].iloc[-1] / frame["volume"].iloc[-51:-1].mean())
    ret_1d = float(c.iloc[-1] / c.iloc[-2] - 1)
    rvol20 = float(np.log(c).diff().iloc[-20:].std() * np.sqrt(252))
    return {"bb_pct": bb_pct, "nr7": nr7, "last_vol_x": vol_x, "last_ret": ret_1d, "rvol20": rvol20,
            "bar_date": frame.index[-1].date().isoformat()}


def earnings_calendar(now_ny):
    """Nasdaq's public calendar: every US report dated today through the next few sessions."""
    rows = []
    for day in pd.bdate_range(now_ny.date(), periods=EARNINGS_SESSIONS):
        url = f"https://api.nasdaq.com/api/calendar/earnings?date={day.date()}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
        for x in (data.get("data") or {}).get("rows") or []:
            rows.append({"ticker": x["symbol"].replace("/", "."), "date": day.date().isoformat(),
                         "when": {"time-after-hours": "after close", "time-pre-market": "before open"}
                         .get(x.get("time"), "time not set"),
                         "eps_forecast": x.get("epsForecast") or "", "n_est": x.get("noOfEsts") or ""})
    return pd.DataFrame(rows, columns=["ticker", "date", "when", "eps_forecast", "n_est"])


def reaction_returns(frame, stamps, today):
    """Day-1 close-to-close move after each past report. A stamp at or after noon is an after-close
    report (reaction next session); earlier is before the open (reaction the same session)."""
    out = []
    idx = frame.index
    for ts in stamps:
        day = pd.Timestamp(ts.date())
        if day.date() >= today:
            continue
        i = idx.searchsorted(day)
        if i >= len(idx):
            continue
        # ponytail: a stamp at midnight is treated as after close, the usual case for these names
        after_close = idx[i] == day and (ts.hour >= 12 or ts.hour == 0)
        base, react = (i, i + 1) if after_close else (i - 1, i)
        if base < 0 or react >= len(idx):
            continue
        out.append(float(frame["close"].iloc[react] / frame["close"].iloc[base] - 1))
    return out


def earnings_detail(ticker, frame, event, today, spot):
    """Past day-1 reactions (yfinance dates) and the option straddle spanning the event."""
    detail = {}
    try:
        ed = yf.Ticker(yahoo(ticker)).get_earnings_dates(limit=16)
        moves = reaction_returns(frame, [ts.tz_convert(NY) if ts.tzinfo else ts for ts in ed.index], today)
        if moves:
            detail.update(past_n=len(moves), past_abs=float(np.mean(np.abs(moves))),
                          past_up=int(sum(m > 0 for m in moves)), last_move=moves[0])
    except Exception as e:  # yfinance scraping breaks from time to time; the flag still stands
        detail["past_error"] = type(e).__name__
    try:
        react = pd.Timestamp(event["date"])
        if event["when"] != "before open":
            react += pd.offsets.BDay(1)
        t = yf.Ticker(yahoo(ticker))
        expiry = next((e for e in t.options if pd.Timestamp(e) >= react), None)
        if expiry:
            chain = t.option_chain(expiry)
            legs = []
            for side in (chain.calls, chain.puts):
                row = side.iloc[(side.strike - spot).abs().argmin()]
                mid = (row.bid + row.ask) / 2 if row.bid > 0 and row.ask > 0 else row.lastPrice
                legs.append(float(mid))
            detail.update(expiry=expiry, implied_move=sum(legs) / spot)
    except Exception as e:
        detail["options_error"] = type(e).__name__
    return detail


def tag_title(title):
    """Materiality tags for one headline; empty for noise or nothing material."""
    if NEWS_NOISE.search(title):
        return []
    return [tag for tag, pattern in NEWS_TAGS.items() if re.search(pattern, title, re.I)]


def fetch_news(name, now_ts):
    params = urllib.parse.urlencode({"keyword": name, "size": 20, "news_type": 1, "lang": "en", "sort_type": 2})
    req = urllib.request.Request(f"{NEWS_URL}?{params}", headers={"User-Agent": "moomoo-news-search/0.0.2 (Skill)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    if data.get("code") != 0:
        raise RuntimeError(data.get("message"))
    items = []
    for x in data.get("data") or []:
        if "<em>" not in x["title"]:  # the API highlights matches; unhighlighted items are off-topic
            continue
        t = int(x["publish_time"])
        t = t / 1000 if t > 1e12 else t
        if now_ts - t > NEWS_HOURS * 3600:
            continue
        title = html.unescape(re.sub(r"<[^>]+>", "", x["title"]))
        items.append({"title": title, "ts": t, "url": x["url"], "tags": tag_title(title)})
    return items


def plain(v):
    """JSON-safe scalar: numpy types unwrapped, NaN as None."""
    v = v.item() if hasattr(v, "item") else v
    return None if isinstance(v, float) and np.isnan(v) else v


def score(row):
    """Points and plain-language reasons for one ticker's flags."""
    pts, why = 0.0, []
    if row.get("earnings_date"):
        pts += WEIGHTS["earnings"]
        line = f"Earnings {row['earnings_date']} {row['earnings_when']}"
        if row.get("implied_move"):
            line += f"; options imply ±{row['implied_move']:.1%}"
        if row.get("past_abs"):
            line += f"; day-1 moves over the last 2 years average {row['past_abs']:.1%} ({int(row["past_up"])}/{int(row["past_n"])} up)"
        why.append(line)
    if row.get("vcp_status"):
        key = "vcp_actionable" if row.get("vcp_actionable") else "vcp"
        pts += WEIGHTS[key]
        why.append(f"VCP {row['vcp_setup']} ({int(row['vcp_legs'])} contractions, {row['vcp_tier']}): "
                   f"{row['vcp_status']}, pivot ${row['vcp_pivot']:,.2f}"
                   + ("; trend stack intact" if row.get("vcp_stage2") else ""))
    if row.get("bb_pct") is not None and row["bb_pct"] <= SQUEEZE_PCT:
        pts += WEIGHTS["squeeze"]
        why.append(f"Squeeze: Bollinger width in the narrowest {max(row['bb_pct'], 1 / 126):.0%} of 6 months"
                   + (", narrowest range of 7 days" if row.get("nr7") else ""))
    material = [n for n in row.get("news", []) if n["tags"]]
    if material:
        pts += WEIGHTS["news"]
        tags = sorted({t for n in material for t in n["tags"]})
        if len(tags) >= 2 or len(material) >= 4:
            pts += WEIGHTS["news_multi"]
        why.append(f"News ({NEWS_HOURS}h): {len(material)} material item(s): {', '.join(tags)}")
    if abs(row.get("chg") or 0) >= 0.05 and (row.get("volume_ratio") or 0) >= 1.5:
        pts += WEIGHTS["mover"]
        why.append(f"Moving today: {row['chg']:+.1%} on {row['volume_ratio']:.1f}x usual volume")
    if (row.get("last_vol_x") or 0) >= 2 and row.get("last_ret") is not None and abs(row["last_ret"]) <= 0.015:
        pts += WEIGHTS["quiet_volume"]
        why.append(f"Last session: {row['last_vol_x']:.1f}x average volume on a {row['last_ret']:+.1%} move")
    if row.get("watchlist"):
        pts += WEIGHTS["watchlist"]
    return pts, why


def run(watchlist, with_news=True):
    now_ny = dt.datetime.now(NY)
    today = now_ny.date()
    log = lambda msg: print(f"[{dt.datetime.now(HK):%H:%M:%S}] {msg}", flush=True)

    log("OpenD universe and quotes")
    uni = load_universe(watchlist)
    log(f"{len(uni)} names; yfinance daily bars")
    frames, spy = load_bars(uni.index.tolist(), now_ny)
    log(f"{len(frames)} with history; VCP detector")
    vcp = vcp_setups(frames, spy)
    sq = pd.DataFrame.from_dict({t: squeeze_stats(f) for t, f in frames.items()}, orient="index")

    log("earnings calendar")
    cal = earnings_calendar(now_ny)
    started = (cal.date == today.isoformat()) & (cal.when == "before open") & (now_ny.time() >= dt.time(9, 30))
    cal = cal[cal.ticker.isin(uni.index) & ~started].drop_duplicates("ticker").set_index("ticker")

    rows = uni.join(sq).join(vcp.add_prefix("vcp_"))
    rows = rows.rename(columns={"vcp_setup_type": "vcp_setup", "vcp_n_contractions": "vcp_legs",
                                "vcp_resistance": "vcp_pivot"})
    rows["earnings_date"] = cal["date"]
    rows["earnings_when"] = cal["when"]
    rows["eps_forecast"] = cal["eps_forecast"]

    log(f"earnings detail for {len(cal)} names")
    with ThreadPoolExecutor(6) as pool:
        details = dict(zip(cal.index, pool.map(
            lambda t: earnings_detail(t, frames[t], cal.loc[t], today, uni.loc[t, "last_price"])
            if t in frames else {}, cal.index)))
    extra = pd.DataFrame.from_dict(details, orient="index")
    rows = rows.join(extra) if not extra.empty else rows

    news = {}
    if with_news:
        flagged = rows[rows.watchlist | rows.earnings_date.notna() | rows.vcp_actionable.eq(True)
                       | rows.bb_pct.le(SQUEEZE_PCT) | ((rows.chg.abs() >= 0.05) & (rows.volume_ratio >= 1.5))]
        log(f"news for {len(flagged)} names")
        now_ts = time.time()

        for t in flagged.index:  # sequential: the API allows ~14 calls in a burst
            for attempt in range(3):
                try:
                    news[t] = fetch_news(rows.loc[t, "name"], now_ts)
                    break
                except urllib.error.HTTPError as e:
                    if e.code not in (429, 439) or attempt == 2:
                        log(f"news failed for {t}: {e}")
                        break
                    time.sleep(10)
                except Exception as e:
                    log(f"news failed for {t}: {e}")
                    break
            time.sleep(0.8)

    records = []
    for t, r in rows.iterrows():
        rec = {k: plain(v) for k, v in r.to_dict().items()}
        rec["ticker"], rec["news"] = t, news.get(t, [])
        rec["points"], rec["why"] = score(rec)
        records.append(rec)
    records.sort(key=lambda r: (-r["points"], -(r["mcap"] or 0)))
    picks = [r["ticker"] for r in records if r["points"] - WEIGHTS["watchlist"] * r["watchlist"] >= 2][:TOP_PICKS]

    result = {
        "generated_hkt": dt.datetime.now(HK).strftime("%Y-%m-%d %H:%M"),
        "generated_et": now_ny.strftime("%Y-%m-%d %H:%M"),
        "quote_time": str(uni.update_time.max()),
        "bar_date": sq.bar_date.mode().iloc[0] if len(sq) else None,
        "universe": len(uni), "with_history": len(frames), "news_checked": with_news,
        "weights": WEIGHTS, "squeeze_pct": SQUEEZE_PCT, "picks": picks, "rows": records,
    }
    stamp = now_ny.strftime("%Y%m%d_%H%M")
    (HERE / "runs").mkdir(exist_ok=True)
    (HERE / "runs" / f"{stamp}.json").write_text(json.dumps(result, default=str, indent=1), encoding="utf-8")
    from page import render
    (HERE / "docs").mkdir(exist_ok=True)  # GitHub Pages serves docs/ from main
    (HERE / "docs" / "index.html").write_text(render(result), encoding="utf-8")
    log(f"picks: {', '.join(picks)}; wrote runs/{stamp}.json and docs/index.html")
    return stamp


def publish(stamp):
    """Commit this run's page and record, then push to the GitHub remote."""
    import subprocess
    git = lambda *a: subprocess.run(["git", *a], cwd=HERE, check=True)
    git("add", "docs/index.html", f"runs/{stamp}.json")
    git("commit", "-m", f"Radar run {stamp} ET")
    git("push")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-news", action="store_true")
    ap.add_argument("--publish", action="store_true", help="commit and push docs/ to GitHub Pages")
    args = ap.parse_args()
    wl = [t.strip().upper() for t in (HERE / "watchlist.txt").read_text().split() if t.strip()]
    stamp = run(wl, with_news=not args.no_news)
    if args.publish:
        publish(stamp)
