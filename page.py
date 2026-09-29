"""Render one radar run as a static page: stocks to watch, watchlist, earnings, VCP, squeezes, news."""
import datetime as dt
from html import escape
from zoneinfo import ZoneInfo

HK = ZoneInfo("Asia/Hong_Kong")

CSS = """
:root { --bg:#f5f6f8; --panel:#fff; --ink:#16202e; --muted:#5b6677; --line:#dde2ea; --accent:#1f5fbf;
        --up:#137333; --down:#b3261e; --chip:#eef2f8; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#11151c; --panel:#1a2029; --ink:#e6ebf2; --muted:#9aa5b5; --line:#2c3440; --accent:#7fb0ff;
          --up:#5fd08a; --down:#ff8a80; --chip:#232b36; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink); line-height:1.5;
       font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans",sans-serif; }
main { max-width:1180px; margin:0 auto; padding:20px 16px 48px; }
h1 { font-size:24px; margin:0 0 4px; } h2 { font-size:18px; margin:32px 0 10px; }
.meta, .note, .source { color:var(--muted); font-size:13px; }
.cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:12px; }
.card { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px 16px; }
.card h3 { margin:0; font-size:17px; display:flex; justify-content:space-between; gap:8px; }
.card ul { margin:8px 0 0; padding-left:18px; } .card li { margin:2px 0; }
.news { list-style:none; padding:0; margin:10px 0 0; border-top:1px solid var(--line); }
.news li { padding:6px 0 0; } .news a { color:var(--ink); }
.chip { display:inline-block; background:var(--chip); border-radius:10px; padding:0 7px; font-size:12px;
        margin-left:4px; color:var(--muted); }
.up { color:var(--up); } .down { color:var(--down); }
.wrap { overflow-x:auto; background:var(--panel); border:1px solid var(--line); border-radius:8px; }
table { border-collapse:collapse; width:100%; font-size:13.5px; font-variant-numeric:tabular-nums; }
th, td { padding:6px 10px; border-bottom:1px solid var(--line); text-align:right; white-space:nowrap; }
th:first-child, td:first-child, td.l, th.l { text-align:left; }
th { color:var(--muted); font-weight:600; cursor:pointer; position:sticky; top:0; background:var(--panel); }
tr:last-child td { border-bottom:0; }
a { color:var(--accent); }
.empty { padding:12px 16px; color:var(--muted); }
"""

SORT_JS = """
document.querySelectorAll('table.sortable th').forEach((th, col) => th.addEventListener('click', () => {
  const body = th.closest('table').tBodies[0], asc = th.dataset.dir !== 'asc';
  th.closest('tr').querySelectorAll('th').forEach(h => delete h.dataset.dir); th.dataset.dir = asc ? 'asc' : 'desc';
  const key = r => { const c = r.cells[col], v = c.dataset.v ?? c.textContent; const n = parseFloat(v);
                     return isNaN(n) ? v.toLowerCase() : n; };
  [...body.rows].sort((a, b) => { const x = key(a), y = key(b);
    return (x < y ? -1 : x > y ? 1 : 0) * (asc ? 1 : -1); }).forEach(r => body.appendChild(r));
}));
"""


def pct(v, signed=False, digits=1):
    if v is None:
        return "—"
    return f"{v:+.{digits}%}" if signed else f"{v:.{digits}%}"


def signed_cell(v):
    cls = "" if v is None else ("up" if v > 0 else "down" if v < 0 else "")
    return f'<td class="{cls}" data-v="{"" if v is None else v}">{pct(v, True)}</td>'


def num_cell(v, text):
    return f'<td data-v="{"" if v is None else v}">{text}</td>'


def when(ts):
    return dt.datetime.fromtimestamp(ts, HK).strftime("%d %b %H:%M HKT")


def news_list(items, limit=3):
    items = [n for n in items if n["tags"]][:limit]
    if not items:
        return ""
    lis = "".join(
        f'<li><a href="{escape(n["url"])}" target="_blank" rel="noopener">{escape(n["title"])}</a>'
        f'<div class="source">moomoo news · {when(n["ts"])}'
        + "".join(f'<span class="chip">{escape(t)}</span>' for t in n["tags"]) + "</div></li>"
        for n in items if n["url"].startswith("https://"))
    return f'<ul class="news">{lis}</ul>'


def pick_card(r):
    chg = r.get("chg")
    cls = "up" if (chg or 0) > 0 else "down" if (chg or 0) < 0 else ""
    why = "".join(f"<li>{escape(w)}</li>" for w in r["why"])
    star = '<span class="chip">watchlist</span>' if r.get("watchlist") else ""
    return (f'<div class="card"><h3><span>{escape(r["ticker"])} {star}</span>'
            f'<span>${r["last_price"]:,.2f} <span class="{cls}">{pct(chg, True)}</span></span></h3>'
            f'<div class="meta">{escape(str(r.get("name") or ""))} · {escape(str(r.get("plate") or ""))}'
            f' · {r["points"]:g} pts</div><ul>{why}</ul>{news_list(r.get("news", []))}</div>')


def table(headers, rows, empty):
    if not rows:
        return f'<div class="wrap"><div class="empty">{empty}</div></div>'
    head = "".join(f'<th class="l">{h}</th>' if i == 0 else f"<th>{h}</th>" for i, h in enumerate(headers))
    return (f'<div class="wrap"><table class="sortable"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def ticker_cell(r):
    star = " ★" if r.get("watchlist") else ""
    return f'<td class="l" data-v="{escape(r["ticker"])}"><b>{escape(r["ticker"])}</b>{star}</td>'


def render(run):
    rows = run["rows"]
    by = {r["ticker"]: r for r in rows}
    picks = [by[t] for t in run["picks"]]

    wl = sorted((r for r in rows if r.get("watchlist")), key=lambda r: -r["points"])
    wl_rows = [
        "<tr>" + ticker_cell(r) + num_cell(r["last_price"], f'${r["last_price"]:,.2f}') + signed_cell(r.get("chg"))
        + num_cell(r.get("volume_ratio"), f'{r["volume_ratio"]:.1f}x' if r.get("volume_ratio") else "—")
        + signed_cell(r.get("off_high")) + num_cell(r.get("rvol20"), pct(r.get("rvol20"), digits=0))
        + f'<td class="l">{escape(r.get("earnings_date") or "")} {escape(r.get("earnings_when") or "")}</td>'
        + f'<td class="l">{escape(r.get("vcp_status") or "")}</td>'
        + num_cell(r.get("bb_pct"), pct(r.get("bb_pct"), digits=0))
        + num_cell(len([n for n in r.get("news", []) if n["tags"]]), str(len([n for n in r.get("news", []) if n["tags"]])))
        + num_cell(r["points"], f'{r["points"]:g}') + "</tr>" for r in wl]

    earn = sorted((r for r in rows if r.get("earnings_date")), key=lambda r: (r["earnings_date"], -(r["mcap"] or 0)))
    earn_rows = []
    for r in earn:
        earn_rows.append(
            "<tr>" + ticker_cell(r) + f'<td class="l">{r["earnings_date"]}</td>'
            f'<td class="l">{escape(r["earnings_when"])}</td><td>{escape(str(r.get("eps_forecast") or "—"))}</td>'
            + num_cell(r.get("implied_move"), "±" + pct(r["implied_move"]) if r.get("implied_move") else "—")
            + num_cell(r.get("past_abs"), pct(r.get("past_abs")))
            + (f'<td>{int(r["past_up"])}/{int(r["past_n"])}</td>' if r.get("past_n") else "<td>—</td>")
            + signed_cell(r.get("last_move")) + num_cell(r["last_price"], f'${r["last_price"]:,.2f}') + "</tr>")

    vcp = sorted((r for r in rows if r.get("vcp_status")),
                 key=lambda r: (not r.get("vcp_actionable"), -(r.get("vcp_score") or 0)))[:25]
    vcp_rows = [
        "<tr>" + ticker_cell(r) + f'<td class="l">{escape(r["vcp_setup"])}</td><td>{int(r["vcp_legs"])}</td>'
        f'<td class="l">{"yes" if r.get("vcp_actionable") else "no"}</td><td class="l">{escape(r["vcp_status"])}</td>'
        + num_cell(r["vcp_pivot"], f'${r["vcp_pivot"]:,.2f}')
        + num_cell(r.get("vcp_vol_dryup_ratio"), f'{r["vcp_vol_dryup_ratio"]:.2f}' if r.get("vcp_vol_dryup_ratio") else "—")
        + f'<td class="l">{"yes" if r.get("vcp_stage2") else "no"}</td>'
        + num_cell(r.get("vcp_score"), f'{r["vcp_score"]:.2f}' if r.get("vcp_score") is not None else "—") + "</tr>"
        for r in vcp]

    sq = sorted((r for r in rows if r.get("bb_pct") is not None and r["bb_pct"] <= run["squeeze_pct"]),
                key=lambda r: (r["bb_pct"], -(r["mcap"] or 0)))[:25]
    sq_rows = [
        "<tr>" + ticker_cell(r) + num_cell(r["bb_pct"], pct(r["bb_pct"], digits=0))
        + f'<td class="l">{"yes" if r.get("nr7") else "no"}</td>'
        + num_cell(r.get("rvol20"), pct(r.get("rvol20"), digits=0)) + signed_cell(r.get("off_high"))
        + num_cell(r["last_price"], f'${r["last_price"]:,.2f}') + f'<td class="l">{escape(str(r.get("plate") or ""))}</td></tr>'
        for r in sq]

    news_blocks = []
    for r in sorted(rows, key=lambda r: -r["points"]):
        items = [n for n in r.get("news", []) if n["tags"]]
        if items:
            news_blocks.append(f'<div class="card"><h3><span>{escape(r["ticker"])}</span>'
                               f'<span class="meta">{escape(str(r.get("name") or ""))}</span></h3>'
                               f'{news_list(items, limit=6)}</div>')

    w = run["weights"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Watchlist Radar</title><style>{CSS}</style></head>
<body><main>
<h1>Watchlist Radar</h1>
<div class="meta">Run {run["generated_hkt"]} HKT ({run["generated_et"]} ET) · live quotes to {escape(run["quote_time"])} ET ·
technical flags on completed bars to {run["bar_date"]} · {run["universe"]} names scanned ({run["with_history"]} with history)</div>

<h2>Stocks to watch</h2>
<p class="note">Names most likely to move in the next few sessions, ranked by flags: earnings soon ({w["earnings"]} pts),
an actionable VCP coil ({w["vcp_actionable"]}; other VCP {w["vcp"]}), a volatility squeeze ({w["squeeze"]}),
material news in 48h ({w["news"]}, +{w["news_multi"]} if broad), moving today ({w["mover"]}), heavy volume on a quiet
day ({w["quiet_volume"]}), on your watchlist ({w["watchlist"]}). A pick needs at least 2 points from flags.</p>
<div class="cards">{"".join(pick_card(r) for r in picks) or '<div class="card">No name reached the threshold today.</div>'}</div>

<h2>Your watchlist</h2>
{table(["Ticker", "Price", "Today", "Vol vs usual", "Off 52w high", "20d vol", "Earnings", "VCP", "BB width pct",
        "News 48h", "Points"], wl_rows, "Watchlist is empty.")}

<h2>Earnings in the next few sessions</h2>
<p class="note">Implied move = at-the-money straddle on the first expiry after the report, as a share of price.
Past day-1 moves cover reports in the last 2 years (dates from Yahoo Finance). Reports already reacted to today are left out.</p>
{table(["Ticker", "Date", "When", "EPS est.", "Implied move", "Avg day-1 (2y)", "Up", "Last day-1", "Price"],
       earn_rows, "No reports in the universe in the next few sessions.")}

<h2>VCP setups</h2>
<p class="note">Admiralty VCP detector, unchanged: forming coils and confirmed bases still under their pivot.
Actionable = at least 3 contractions and within 5% below the pivot. Dry-up = base volume / pre-base volume.</p>
{table(["Ticker", "Setup", "Legs", "Actionable", "Status", "Pivot", "Dry-up", "Trend stack", "Score"],
       vcp_rows, "No coils today.")}

<h2>Volatility squeezes</h2>
<p class="note">20-day Bollinger width in the narrowest {run["squeeze_pct"]:.0%} of the last 6 months. NR7 = narrowest daily range of 7 sessions.</p>
{table(["Ticker", "BB width pct", "NR7", "20d vol", "Off 52w high", "Price", "Group"], sq_rows, "No squeezes today.")}

<h2>Material news, last 48 hours</h2>
<p class="note">Checked for the watchlist and every flagged name. Tags come from headline keywords; law-firm ads and
market-wrap roundups are dropped.</p>
<div class="cards">{"".join(news_blocks) or '<div class="card">No material news found.</div>'}</div>

<p class="note" style="margin-top:32px">Sources: universe and live quotes from moomoo OpenD; daily bars, past earnings
dates and options from Yahoo Finance (yfinance); earnings calendar from
<a href="https://www.nasdaq.com/market-activity/earnings">Nasdaq</a>; news from moomoo news search, linked per item.
Flags are hand-weighted and not yet validated against history. For research only; not investment advice.</p>
</main><script>{SORT_JS}</script></body></html>"""
