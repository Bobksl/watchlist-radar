"""Render one radar run as a static page: stocks to watch, watchlist, earnings, VCP, squeezes, news."""
import datetime as dt
import json
from decimal import Decimal
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
        + (f'<div class="meta">{escape(n["why"])}</div>' if n.get("why") else "")
        + f'<div class="source">moomoo news · {when(n["ts"])}'
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
            f' · {r["points"]:g} pts</div>{brief(r)}<ul>{why}</ul>{levels(r)}{card_line(r.get("card"))}'
            f'{news_list(r.get("news", []))}</div>')


CHECK_NAMES = {"historical_facts": "Historical facts", "target_arithmetic": "Target arithmetic",
               "implied_assumptions": "Implied assumptions", "guidance_record": "Guidance record",
               "target_distribution": "Target distribution"}


def verdict_counts(check):
    counts = dict(check.get("licensed_counts") or {})
    for c in check["claims"]:
        counts[c["verdict"]] = counts.get(c["verdict"], 0) + 1
    return ", ".join(f"{n} {v}" for v, n in sorted(counts.items()))


def card_line(card):
    """One-line Street Validator summary for a pick card."""
    if not card:
        return ""
    parts = [f'{CHECK_NAMES.get(c["name"], c["name"])} {c["status"]}'
             + (f' ({verdict_counts(c)})' if verdict_counts(c) else "")
             for c in card["checks"] if c["status"] != "not_supplied"]
    skipped = sum(c["status"] == "not_supplied" for c in card["checks"])
    text = "; ".join(parts) + (f"; {skipped} checks not supplied" if skipped else "")
    return (f'<p class="source">Street Validator ({escape(card["as_of"])}): {escape(text)} · '
            f'<a href="#validator-{escape(card["ticker"])}">details</a></p>')


def show_value(claimed):
    """A decimal string as written by the validator; formatted without passing through float."""
    d = Decimal(claimed["value"])
    if claimed["unit"] == "USD":
        return f"${d / 10 ** 9:,.2f}bn" if abs(d) >= 10 ** 9 else f"${d:,}"
    return f'{d:,} {escape(claimed["unit"])}'


def validator_html(cards, local):
    if not cards:
        return '<div class="wrap"><div class="empty">No validator card for any name in today\'s universe.</div></div>'
    blocks = []
    for t, card in sorted(cards.items()):
        checks = []
        for c in card["checks"]:
            rows = []
            for cl in c["claims"]:
                src = cl["source"]
                meas = "; ".join(f'{m["name"].replace("_", " ")} {m["value"]}{m["unit"] if m["unit"] in ("%", "x") else " " + m["unit"]}'
                                 for m in cl.get("measurements", []))
                link = src["link"]
                where = (f'<a href="{escape(link)}" target="_blank" rel="noopener">{escape(src["publisher"])}</a>'
                         if link.startswith("https://") else escape(src["publisher"]))
                rows.append(f'<tr><td class="l">{escape(cl["subject"])}</td><td>{show_value(cl["claimed"])}</td>'
                            f'<td class="l"><b>{escape(cl["verdict"])}</b></td><td class="l">{escape(cl["reason"])}'
                            + (f'<div class="source">{escape(meas)}</div>' if meas else "")
                            + f'</td><td class="l">{where} {escape(src["date"])}, {escape(src["locator"])}'
                            f'{" (licensed)" if src.get("licence") == "licensed" else ""}</td></tr>')
            hidden = c.get("licensed_counts")
            note = (f'<div class="empty">Licensed source: {sum(hidden.values())} claim(s), '
                    f'{escape(", ".join(f"{n} {v}" for v, n in sorted(hidden.items())))}. '
                    f'Values shown on the local page only.</div>') if hidden else ""
            body = (f'<div class="wrap"><table><thead><tr><th class="l">Claim</th><th>Claimed</th><th class="l">Verdict</th>'
                    f'<th class="l">Reason</th><th class="l">Source</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
                    if rows else "")
            checks.append(f'<h3 style="font-size:15px;margin:14px 0 6px">{c["check"]}. '
                          f'{escape(CHECK_NAMES.get(c["name"], c["name"]))}: <span class="chip">{escape(c["status"])}</span></h3>'
                          f'{body}{note}')
        blocks.append(f'<div class="card" id="validator-{escape(t)}" style="margin-bottom:12px"><h3><span>{escape(t)}</span>'
                      f'<span class="meta">computed {escape(card["as_of"])} · filings to {escape(card["facts_as_of"])}'
                      f' · {escape(card["spec"])}</span></h3>{"".join(checks)}</div>')
    scope = ("Local page: licensed claim values shown." if local
             else "Public page: claims from licensed sources are reduced to verdict counts.")
    return f'<p class="note">{scope}</p>' + "".join(blocks)


def brief(r):
    return f'<p style="margin:8px 0 0"><b>{escape(r["news_brief"])}</b></p>' if r.get("news_brief") else ""


def levels(r):
    """Reference prices from completed bars, as distance from the live price."""
    px = r.get("last_price")
    if not px or r.get("hi20") is None:
        return ""
    parts = [f'20-day high ${r["hi20"]:,.2f} ({r["hi20"] / px - 1:+.1%})',
             f'20-day low ${r["lo20"]:,.2f} ({r["lo20"] / px - 1:+.1%})',
             f'ATR ${r["atr14"]:,.2f} ({r["atr14"] / px:.1%})']
    if r.get("vcp_pivot"):
        piv, low = r["vcp_pivot"], r["vcp_last_low"]
        plan = f'VCP pivot ${piv:,.2f} ({piv / px - 1:+.1%}), coil low ${low:,.2f} ({low / px - 1:+.1%})'
        if piv > low:  # runner exit from the VCP study: stop at the coil low, 3R arms the trailing stop
            plan += f', 3R ${piv + 3 * (piv - low):,.2f} arms a trailing stop'
        parts.insert(0, plan)
    if r.get("implied_move"):
        m = r["implied_move"]
        parts.insert(0, f'earnings range ${px * (1 - m):,.2f} to ${px * (1 + m):,.2f}')
    return f'<p class="source">Levels: {escape(" · ".join(parts))}</p>'


def scoreboard_html(board):
    """Past picks and how each flag's names moved vs the typical name in the same run."""
    if not board or not board["picks"]:
        return ('<div class="wrap"><div class="empty">No earlier run has a completed session after it yet. '
                'Results appear from the next run onward.</div></div>')
    names = {"pick": "Stocks to watch", "earnings": "Earnings soon", "peer_earnings": "Peer reports",
             "vcp": "VCP coil", "squeeze": "Squeeze", "news": "Material news", "mover": "Moving on the day",
             "quiet_volume": "Quiet heavy volume"}
    flag_rows = ["<tr>" + f'<td class="l">{escape(names.get(f["flag"], f["flag"]))}</td>'
                 + "".join(num_cell(f[f"ratio_{h}"], f'{f[f"ratio_{h}"]:.2f}x' if f[f"ratio_{h}"] else "—")
                           + num_cell(f[f"n_{h}"], str(f[f"n_{h}"])) for h in (1, 5)) + "</tr>"
                 for f in sorted(board["flags"], key=lambda f: -(f["ratio_1"] or 0))]
    pick_rows = ["<tr>" + f'<td class="l">{escape(p["run"])}</td><td class="l"><b>{escape(p["ticker"])}</b></td>'
                 f'<td class="l">{escape(", ".join(names.get(f, f) for f in p["flags"]))}</td>'
                 + signed_cell(p.get("ret_1")) + signed_cell(p.get("ret_5")) + "</tr>"
                 for p in board["picks"][:25]]
    return (table(["Flag", "Next session vs typical", "n", "5 sessions vs typical", "n"], flag_rows, "")
            + '<div style="height:12px"></div>'
            + table(["Run (ET)", "Pick", "Flags", "Next session", "5 sessions"], pick_rows, ""))


def table(headers, rows, empty):
    if not rows:
        return f'<div class="wrap"><div class="empty">{empty}</div></div>'
    head = "".join(f'<th class="l">{h}</th>' if i == 0 else f"<th>{h}</th>" for i, h in enumerate(headers))
    return (f'<div class="wrap"><table class="sortable"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def ticker_cell(r):
    star = " ★" if r.get("watchlist") else ""
    return f'<td class="l" data-v="{escape(r["ticker"])}"><b>{escape(r["ticker"])}</b>{star}</td>'


def render(run, local=False):
    cards = run.get("cards") or {}
    rows = [{**r, "card": cards.get(r["ticker"])} for r in run["rows"]]
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
        + f'<td class="l">{ {True: "pass", False: "fail"}.get(r.get("vcp_leg_floor"), "n/a") }</td>'
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
                               f'{brief(r)}{news_list(items, limit=6)}</div>')

    w = run["weights"]
    coverage = {}
    for r in rows:
        status = r.get("coverage", {}).get("news", "unknown_legacy")
        coverage[status] = coverage.get(status, 0) + 1
    coverage_note = escape(", ".join(f"{k}: {v}" for k, v in sorted(coverage.items())))
    generated = run.get("generated_utc")
    if not generated and run.get("generated_et"):
        generated = dt.datetime.strptime(run["generated_et"], "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/New_York")).isoformat()
    freshness_js = """
const generated = GENERATED, deadline = DEADLINE, runId = RUN_ID;
const refreshNode = document.getElementById('refresh-health');
function health(s) {
  const stale = Date.now() > Date.parse(deadline || generated) + (deadline ? 0 : 36*3600000);
  refreshNode.textContent = (stale ? 'STALE snapshot. ' : 'Snapshot current. ') +
    (s && s.scan === 'failed' ? 'Latest scan failed: '+s.error+'. Last good content retained. ' : '') +
    'Last successful scan: '+(generated || 'unknown')+'. Checks for updates every 60 seconds.';
}
async function poll() {
  try {
    const response = await fetch('status.json?t='+Date.now(), {cache:'no-store'});
    if (!response.ok) throw new Error('status unavailable');
    const s = await response.json();
    if (s.scan === 'success' && s.run && s.run > runId)
      { location.reload(); return; }
    health(s);
  } catch(e) { health(null); refreshNode.textContent += ' Refresh status unavailable.'; }
}
health(null); poll(); setInterval(poll, 60000);
""".replace("GENERATED", json.dumps(generated)).replace("DEADLINE", json.dumps(run.get("stale_after"))).replace(
        "RUN_ID", json.dumps((run.get("generated_et") or "").replace("-", "").replace(" ", "_").replace(":", "")))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Watchlist Radar</title><style>{CSS}</style></head>
<body><main>
<h1>Watchlist Radar</h1>
<p class="note" id="refresh-health" role="status">Snapshot freshness requires JavaScript. Last scan: {escape(generated or 'unknown')}.</p>
<div class="meta">Run {run["generated_hkt"]} HKT ({run["generated_et"]} ET) · live quotes to {escape(run["quote_time"])} ET ·
technical flags on completed bars to {run["bar_date"]} · {run["universe"]} names scanned ({run["with_history"]} with history)</div>
<p class="note">News coverage — {coverage_note}. Skipped, failed and legacy checks do not establish absence of news.
New snapshots convert adjusted technical levels to raw-equivalent prices using the latest completed bar adjustment.
Legacy snapshots may mix adjusted levels and raw quotes. Intraday corporate actions can invalidate this conversion.</p>

<h2>Stocks to watch</h2>
<p class="note">Names most likely to move in the next few sessions, ranked by flags: earnings soon ({w["earnings"]} pts), a theme peer reporting ({w.get("peer_earnings", 0)}),
an actionable VCP coil ({w["vcp_actionable"]}; other VCP {w["vcp"]}), a volatility squeeze ({w["squeeze"]}),
material news in 48h ({w["news"]}, +{w["news_multi"]} if broad), moving today ({w["mover"]}), heavy volume on a quiet
day ({w["quiet_volume"]}), on your watchlist ({w["watchlist"]}). A pick needs at least 2 points from flags.</p>
<div class="cards">{"".join(pick_card(r) for r in picks) or '<div class="card">No name reached the threshold today.</div>'}</div>

<h2>Scoreboard: how earlier flags moved</h2>
<p class="note">From each earlier run's price to the close 1 and 5 sessions later. "vs typical" = the flag's average
absolute move divided by the median absolute move of all names in the same run, pooled over the last 10 runs.
Above 1.00x means the flag found bigger movers than average. Direction is shown for picks only.</p>
{scoreboard_html(run.get("scoreboard"))}

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
Actionable = at least 3 contractions and within 5% below the pivot. Dry-up = base volume / pre-base volume.
Leg floor (VCP study, 2 Oct 2026): every leg of a confirmed 2-leg base at least 2.5 ATR deep; 2-leg bases that
fail it showed no edge over matched controls and earn no points. Not applied to 3+ legs, where it removed the
best bases. The runner plan on pick cards is that study's best exit so far: stop at the coil low, no partial
sale, 3R switches on a trailing stop (mean +0.55R per trade, 44% winners, 495 trades).</p>
{table(["Ticker", "Setup", "Legs", "Actionable", "Status", "Pivot", "Dry-up", "Trend stack", "Leg floor", "Score"],
       vcp_rows, "No coils today.")}

<h2 id="validator">Street Validator</h2>
<p class="note">Claims about these companies checked against SEC filings and their own arithmetic by the Street
Validator (Equity Filings RAG). Verdicts: confirmed, contradicted, unverifiable. The validator states no view on
the stock.</p>
{validator_html(run.get("cards"), local)}

<h2>Volatility squeezes</h2>
<p class="note">20-day Bollinger width in the narrowest {run["squeeze_pct"]:.0%} of the last 6 months. NR7 = narrowest daily range of 7 sessions.</p>
{table(["Ticker", "BB width pct", "NR7", "20d vol", "Off 52w high", "Price", "Group"], sq_rows, "No squeezes today.")}

<h2>Material news, last 48 hours</h2>
<p class="note">Checked for the watchlist and every flagged name. Law-firm ads and market-wrap roundups are dropped
by keyword; relevance and tags checked by {escape(run.get("news_check") or "keywords")}. Summaries are AI-drafted
from the headlines only; follow the link for details.</p>
<div class="cards">{"".join(news_blocks) or '<div class="card">No material items in available coverage; see skipped/failed checks above.</div>'}</div>

<p class="note" style="margin-top:32px">Sources: universe and live quotes from moomoo OpenD; daily bars, past earnings
dates and options from Yahoo Finance (yfinance); earnings calendar from
<a href="https://www.nasdaq.com/market-activity/earnings">Nasdaq</a>; news from moomoo news search, linked per item.
Flags are hand-weighted and not yet validated against history. For research only; not investment advice.</p>
</main><script>{SORT_JS}</script><script>{freshness_js}</script></body></html>"""
