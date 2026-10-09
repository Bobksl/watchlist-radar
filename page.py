"""Render one radar run as a static page: stocks to watch, watchlist, earnings, VCP, squeezes, news."""
import datetime as dt
import json
from decimal import Decimal
from html import escape
from urllib.parse import quote
from zoneinfo import ZoneInfo

from tradingview import chart_url, export_symbols

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
.cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(min(100%,320px),1fr)); gap:12px; }
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
.chart-actions, .tv-controls { display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin-top:12px; }
.chart-actions a, button, select, .download { border:1px solid var(--line); border-radius:4px;
  padding:6px 10px; background:var(--panel); color:var(--accent); font:inherit; }
button { cursor:pointer; } button:disabled { opacity:.5; cursor:default; }
a:focus-visible, button:focus-visible, select:focus-visible, textarea:focus-visible {
  outline:2px solid var(--accent); outline-offset:3px; }
.tv-panel { border-left:3px solid var(--accent); padding:12px 16px; background:var(--panel); margin-top:16px; }
.tv-panel summary { cursor:pointer; font-weight:600; }
.tv-panel textarea { display:block; width:100%; margin-top:8px; padding:8px; color:var(--ink);
  background:var(--bg); border:1px solid var(--line); font:13px/1.5 monospace; }
.overview { margin:16px 0; padding:16px; background:var(--panel); border:1px solid var(--line); }
nav { display:flex; flex-wrap:wrap; gap:8px 16px; margin:16px 0; }
.lane-title { font-size:16px; margin:20px 0 8px; }
input[type=search] { padding:8px; max-width:100%; background:var(--panel); color:var(--ink); border:1px solid var(--line); font:inherit; }
input:focus-visible, summary:focus-visible { outline:2px solid var(--accent); outline-offset:3px; }
.card details { margin-top:12px; } summary { cursor:pointer; }
[hidden] { display:none !important; }
"""

TRADINGVIEW_JS = """
document.getElementById('watchlist-search').addEventListener('input', event => {
  const query = event.target.value.trim().toUpperCase(); let count = 0;
  document.querySelectorAll('#watchlist-table tbody tr').forEach(row => {
    row.hidden = !row.cells[0].textContent.toUpperCase().includes(query); if (!row.hidden) count++;
  });
  document.getElementById('watchlist-count').textContent = count+' watched stocks shown';
});
document.getElementById('tv-interval').addEventListener('change', event => {
  document.querySelectorAll('a[data-tv-intraday]').forEach(link => {
    const url = new URL(link.href); url.searchParams.set('interval', event.target.value); link.href = url.href;
  });
});
document.getElementById('tv-copy').addEventListener('click', async () => {
  const field = document.getElementById('tv-shortlist'), status = document.getElementById('tv-copy-status');
  try { await navigator.clipboard.writeText(field.value); status.textContent = 'Shortlist copied.'; }
  catch(e) { field.focus(); field.select(); status.textContent = 'Select and copy the shortlist manually.'; }
});
"""


def chart_actions(ticker):
    daily, intraday = chart_url(ticker, "D"), chart_url(ticker, "15")
    if not daily:
        return '<p class="note">Chart mapping unavailable</p>'
    name = escape(ticker)
    return (f'<div class="chart-actions"><a href="{escape(daily)}" target="_blank" rel="noopener noreferrer" '
            f'aria-label="{name} daily chart on TradingView">Daily chart ↗</a>'
            f'<a href="{escape(intraday)}" data-tv-intraday target="_blank" rel="noopener noreferrer" '
            f'aria-label="{name} intraday chart on TradingView">Intraday chart ↗</a></div>')


def tradingview_handoff(picks):
    text, missing = export_symbols(picks)
    warning = f'Unmapped: {escape(", ".join(missing))}. Excluded from export.' if missing else 'All shortlist symbols verified.'
    download = (f'<a class="download" download="radar-shortlist.txt" href="data:text/plain;charset=utf-8,{quote(text)}">'
                'Download TXT</a>') if text else ''
    return f'''<details class="tv-panel" open><summary>Free-plan chart handoff</summary>
<p class="note">For a YTD overview, open the daily chart and choose the YTD date range in TradingView.
For single-day timing, open the intraday chart and choose the 1D date range. Candle interval is separate.
Your saved layout and indicators are managed in TradingView; this is not an account sync.</p>
<div class="tv-controls"><label for="tv-interval">Intraday candles</label>
<select id="tv-interval"><option value="15">15 minutes</option><option value="5">5 minutes</option>
<option value="1">1 minute</option></select></div>
<label for="tv-shortlist">Verified attention shortlist</label>
<textarea id="tv-shortlist" rows="2" readonly>{escape(text)}</textarea>
<div class="tv-controls"><button id="tv-copy"{' disabled' if not text else ''}>Copy shortlist</button>{download}
<span id="tv-copy-status" role="status" aria-live="polite"></span></div>
<p class="note">{warning} Native TXT import depends on your TradingView plan; otherwise add symbols manually.
Only verified exchange mappings are linked.</p></details>'''

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
            f' · {r["points"]:g} pts</div>{brief(r)}<ul>{why}</ul>{chart_actions(r["ticker"])}'
            f'<details><summary>Levels, evidence and news</summary>{levels(r)}{card_line(r.get("card"))}'
            f'{news_list(r.get("news", []))}</details></div>')


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
    ticker = escape(r["ticker"])
    url = chart_url(r["ticker"], "D")
    label = (f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer" '
             f'aria-label="{ticker} daily chart on TradingView">{ticker}</a>') if url else ticker
    return f'<td class="l" data-v="{ticker}"><b>{label}</b>{star}</td>'


def benzinga_html(items, briefing):
    if not items:
        return ''
    recent = sum(x['freshness'] == 'recent_7d' for x in items)
    cards = []
    for group in briefing:
        cards.append(f'<article class="card benzinga-item" data-ticker="{escape(group["ticker"])}" data-recent="true" data-bz-kind="briefing">'
                     f'<h3>{escape(group["ticker"])}</h3><p class="meta">{group["events"]} records · {len(group["firms"])} firms · Latest {escape(group["latest_date"])}</p>'
                     f'<p><b>What changed:</b> {escape(", ".join(group["actions"]))}. {escape(group["summary"])}</p>'
                     f'<p><b>Why watch:</b> {escape(group["why_watch"])}</p><p><b>Check next:</b> {escape(group["verify"])}</p>'
                     f'<details><summary>Source firms and event IDs</summary><p>{escape(", ".join(group["firms"]))}</p>'
                     f'<p>{escape(", ".join(group["event_ids"]))}</p></details></article>')
    briefs = ''.join(cards)
    cards = []
    for item in items:
        is_recent = item['freshness'] == 'recent_7d'
        label = {'recent_7d': 'Last 7 days', 'historical': 'Historical', 'future_date_review': 'Future date: review'}[item['freshness']]
        cards.append(f'<article class="card benzinga-item" data-ticker="{escape(item["ticker"])}" data-recent="{str(is_recent).lower()}" data-bz-kind="event" {"" if is_recent else "hidden"}>'
                     f'<h3>{escape(item["ticker"])} · Benzinga</h3><p class="meta">{escape(item["firm"])} · Event {escape(item["date"])} · {label}</p>'
                     f'<p>{escape(item["action"])} · {escape(item["rating"])}</p>'
                     f'<p class="note">Retrieved {escape(item["collected_utc"])}. Latest page only; coverage is incomplete. Rights unknown; commentary unverified. Structured price targets withheld pending source, currency and split checks.</p>'
                     f'<details><summary>Analyst commentary (may contain unverified targets)</summary><p>{escape(item["text"])}</p></details></article>')
    return (f'<section id="benzinga-research"><h2>Benzinga briefing</h2><p>{recent} recent records · {len(briefing)} stocks</p>'
            '<p class="note">Analyst actions reported by Benzinga; factual claims and forecasts remain unverified. '
            'Grouped by stock for review, not independent catalysts. Maintained ratings do not establish a target revision. '
            'Changes since the prior collection are not yet established. Editorial notes expire when their source set changes. '
            'Seven calendar days, using UTC; freshness updates when this page is regenerated.</p>'
            '<div class="tv-controls"><label for="benzinga-search">Ticker</label> '
            '<input id="benzinga-search" type="search" placeholder="e.g. MU" autocomplete="off"> '
            '<label><input id="benzinga-recent" type="checkbox" checked> Last 7 days only</label></div>'
            f'<p id="benzinga-count" role="status" aria-live="polite">Showing {recent} of {len(items)} insights.</p>'
            '<p id="benzinga-empty" class="empty" hidden>No insights match these filters.</p>'
            f'<div class="cards">{briefs}</div><h2>Source insights</h2><div class="cards">{"".join(cards)}</div></section>'
            '''<script>
(() => {
  const section = document.getElementById('benzinga-research');
  const search = section.querySelector('#benzinga-search');
  const recent = section.querySelector('#benzinga-recent');
  const items = [...section.querySelectorAll('.benzinga-item')];
  const total = items.filter(x => x.dataset.bzKind === 'event').length;
  function filter() {
    const query = search.value.trim().toUpperCase();
    let shown = 0;
    for (const item of items) {
      item.hidden = !item.dataset.ticker.includes(query) || (recent.checked && item.dataset.recent !== 'true');
      if (!item.hidden && item.dataset.bzKind === 'event') shown++;
    }
    section.querySelector('#benzinga-count').textContent = `Showing ${shown} of ${total} insights.`;
    section.querySelector('#benzinga-empty').hidden = shown !== 0;
  }
  search.addEventListener('input', filter);
  recent.addEventListener('change', filter);
  filter();
})();
</script>''')


def private_research_html(research):
    if not research:
        return ''
    blocks = []
    for item in research.get('newsletters', []):
        url = str(item.get('article_url', ''))
        title = escape(str(item.get('subject', 'Unknown title')))
        link = f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer">{title}</a>' if url.startswith('https://seekingalpha.com/') else title
        claims = ''.join('<li>'+escape(str(c))+'</li>' for c in item.get('claims', [])[:12])
        blocks.append(f'<div class="card"><h3>{link}</h3><p class="meta">{escape(str(item.get("author") or "Author unknown"))} · {escape(str(item.get("article_date_text") or item.get("message_date_header") or "Date unknown"))} · {escape(str(item.get("evidence_level", "unknown")))}</p>'
                      f'<p class="note">Company attribution requires review; newsletter alert tickers can refer to another company. Licence unknown; claims unverified.</p>'
                      f'<details><summary>Source summary</summary><ul>{claims}</ul></details></div>')
    for report in research.get('reports', []):
        data = report.get('data', {})
        authors = ', '.join(str(a) for a in data.get('analyst_report_by_line') or [])
        blocks.append(f'<div class="card"><h3>{escape(report["ticker"])} · Morningstar</h3><p>{escape(authors)} · Report {escape(str(data.get("analyst_report_update_time_str") or "date unknown"))}</p>'
                      f'<p class="note">Retrieved {escape(report["retrieved_utc"])}. Personal access verified; redistribution rights unknown. Analyst forecasts remain unverified and separate from SEC facts.</p></div>')
    return ('<h2>Private research queue</h2><p class="note">Local only. These sources do not affect attention scores. Missing/unreadable evidence files: '
            +str(len(research.get('unavailable', [])))+'.</p><div class="cards">'+''.join(blocks)+'</div>'
            +benzinga_html(research.get('benzinga', []), research.get('benzinga_briefing', [])))


def render(run, local=False, research=None):
    cards = run.get("cards") or {}
    rows = [{**r, "card": cards.get(r["ticker"])} for r in run["rows"]]
    by = {r["ticker"]: r for r in rows}
    picks = [by[t] for t in run["picks"]]
    watched = [r for r in picks if r.get('watchlist')]
    discoveries = [r for r in picks if not r.get('watchlist')]
    changes = run.get('changes') or {'status': 'no_previous_snapshot'}
    if changes['status'] == 'comparable':
        change_note = ('Compared with '+changes['since']+' ET. Entered shortlist: '+
                       (', '.join(changes['entered']) or 'none')+'. Left: '+
                       (', '.join(changes['left']) or 'none')+'.')
    else:
        change_note = 'Previous comparison unavailable: '+changes['status'].replace('_', ' ')+'.'
    changed = changes.get('flags', {})
    changed_note = '; '.join(t+': added '+(', '.join(v['added']) or 'none')+', removed '+
                            (', '.join(v['removed']) or 'none') for t, v in changed.items() if t in run['picks'])
    moves = [r['chg'] for r in rows if r.get('chg') is not None]
    breadth = f'{sum(v > 0 for v in moves)} advancing · {sum(v < 0 for v in moves)} declining · {sum(v == 0 for v in moves)} unchanged · {len(rows)-len(moves)} missing'

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
    const response = await fetch(STATUS_URL+'?t='+Date.now(), {cache:'no-store'});
    if (!response.ok) throw new Error('status unavailable');
    const s = await response.json();
    if (s.scan === 'success' && s.run && s.run > runId)
      { location.reload(); return; }
    health(s);
  } catch(e) { health(null); refreshNode.textContent += ' Refresh status unavailable.'; }
}
health(null); poll(); setInterval(poll, 60000);
""".replace("GENERATED", json.dumps(generated)).replace("DEADLINE", json.dumps(run.get("stale_after"))).replace(
        "RUN_ID", json.dumps((run.get("generated_et") or "").replace("-", "").replace(" ", "_").replace(":", ""))).replace(
        "STATUS_URL", json.dumps('../docs/status.json' if local else 'status.json'))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Watchlist Radar</title><style>{CSS}</style></head>
<body><main>
<h1>Watchlist Radar</h1>
<nav aria-label="Dashboard sections"><a href="#attention">Attention</a><a href="#watchlist">Watchlist</a><a href="#earnings">Earnings</a><a href="#setups">Technical setups</a><a href="#validator">Street Validator</a></nav>
<p class="note" id="refresh-health" role="status">Snapshot freshness requires JavaScript. Last scan: {escape(generated or 'unknown')}.</p>
<div class="meta">Run {run["generated_hkt"]} HKT ({run["generated_et"]} ET) · live quotes to {escape(run["quote_time"])} ET ·
technical flags on completed bars to {run["bar_date"]} · {run["universe"]} names scanned ({run["with_history"]} with history)</div>
<p class="note">News coverage — {coverage_note}. Skipped, failed and legacy checks do not establish absence of news.
New snapshots convert adjusted technical levels to raw-equivalent prices using the latest completed bar adjustment.
Legacy snapshots may mix adjusted levels and raw quotes. Intraday corporate actions can invalidate this conversion.</p>

<div class="overview"><strong>Scanned-universe breadth</strong><p>{breadth}</p>
<p class="note">This is the Radar universe, not a broad-market index. {escape(change_note)}</p>
{('<p class="note">Shortlist flag changes: '+escape(changed_note)+'</p>') if changed_note else ''}</div>
<h2 id="attention">Stocks to watch</h2>
{tradingview_handoff(run["picks"])}
<p class="note">Names most likely to move in the next few sessions, ranked by flags: earnings soon ({w["earnings"]} pts), a theme peer reporting ({w.get("peer_earnings", 0)}),
an actionable VCP coil ({w["vcp_actionable"]}; other VCP {w["vcp"]}), a volatility squeeze ({w["squeeze"]}),
material news in 48h ({w["news"]}, +{w["news_multi"]} if broad), moving today ({w["mover"]}), heavy volume on a quiet
day ({w["quiet_volume"]}), on your watchlist ({w["watchlist"]}). A pick needs at least 2 points from flags.</p>
<h3 class="lane-title">From your watchlist · {len(watched)}</h3>
<div class="cards">{"".join(pick_card(r) for r in watched) or '<p class="note">No watched name reached the shortlist.</p>'}</div>
<h3 class="lane-title">Discoveries outside your watchlist · {len(discoveries)}</h3>
<div class="cards">{"".join(pick_card(r) for r in discoveries) or '<p class="note">No outsider reached the shortlist.</p>'}</div>
<p class="note">Global rank order: {escape(', '.join(run['picks']) or 'none')}. The lanes preserve this order within each group.</p>

<h2>Scoreboard: how earlier flags moved</h2>
<p class="note">From each earlier run's price to the close 1 and 5 sessions later. "vs typical" = the flag's average
absolute move divided by the median absolute move of all names in the same run, pooled over the last 10 runs.
Above 1.00x means the flag found bigger movers than average. Direction is shown for picks only.
Saved flags remain frozen; archives without saved flags are labelled legacy unknown.</p>
{scoreboard_html(run.get("scoreboard"))}

<h2 id="watchlist">Your watchlist</h2>
<label for="watchlist-search">Find a watched ticker</label> <input id="watchlist-search" type="search" placeholder="e.g. MU">
<p class="note" id="watchlist-count" role="status" aria-live="polite">{len(wl)} watched stocks shown</p>
<div id="watchlist-table">
{table(["Ticker", "Price", "Today", "Vol vs usual", "Off 52w high", "20d vol", "Earnings", "VCP", "BB width pct",
        "News 48h", "Points"], wl_rows, "Watchlist is empty.")}
</div>

<h2 id="earnings">Earnings in the next few sessions</h2>
<p class="note">Implied move = at-the-money straddle on the first expiry after the report, as a share of price.
Past day-1 moves cover reports in the last 2 years (dates from Yahoo Finance). Reports already reacted to today are left out.</p>
{table(["Ticker", "Date", "When", "EPS est.", "Implied move", "Avg day-1 (2y)", "Up", "Last day-1", "Price"],
       earn_rows, "No reports in the universe in the next few sessions.")}

<h2 id="setups">VCP setups</h2>
<p class="note">Admiralty VCP detector, unchanged: forming coils and confirmed bases still under their pivot.
Actionable = at least 3 contractions and within 5% below the pivot. Dry-up = base volume / pre-base volume.
Leg floor: every leg of a confirmed 2-leg base must be at least 2.5 ATR deep to earn points.
The check is not applied to forming coils or 3+ legs. Runner levels use a coil-low stop, no partial sale,
and a 3R trailing-stop trigger. Historical performance has not been revalidated against current inputs.</p>
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
{private_research_html(research) if local else ''}

<p class="note" style="margin-top:32px">Sources: universe and live quotes from moomoo OpenD; daily bars, past earnings
dates and options from Yahoo Finance (yfinance); earnings calendar from
<a href="https://www.nasdaq.com/market-activity/earnings">Nasdaq</a>; news from moomoo news search, linked per item.
Flags are hand-weighted and not yet validated against history. For research only; not investment advice.</p>
</main><script>{SORT_JS}</script><script>{freshness_js}</script><script>{TRADINGVIEW_JS}</script></body></html>"""
