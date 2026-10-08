# Watchlist Radar

Daily or on-demand scan of tech, semiconductor and AI-adjacent US stocks for names likely to move in the next
few sessions. Produces a static page with **Stocks to watch** (about 5), your watchlist, upcoming
earnings with option-implied moves, VCP setups, volatility squeezes, and cited news.

## Run

Start moomoo OpenD and log in, then:

```
C:\Python314\python.exe radar.py
```

About 4 minutes. Output: `docs/index.html` (the page) and `runs/<ET stamp>.json` (every flag for
every name, kept so v2 can score the flags against what happened next). Add `--publish` to commit
and push the page to GitHub Pages, or `--no-news` to skip news. Best run ~30 minutes after the US open.

Watchlist: `watchlist.txt`. Universe: the moomoo industry groups in `PLATES` (radar.py), filtered to
market cap >= $2bn and price >= $5; watchlist names always included.

## Automatic daily delivery (Windows)

The computer must remain on, this Windows user must remain logged in, and moomoo OpenD must remain
logged in on localhost:11111. The Admiralty detector path in `radar.py` must exist. There is no cloud
collector. Git credentials must work without an interactive prompt; GitHub Pages must serve `docs/`
from `main`. Optional validator cards and DeepSeek credentials are not required for a valid scan.

Install the calendar in ignored local storage and preflight from this repository:

```powershell
C:\Python314\python.exe -m pip install --target local/dependencies -r requirements-calendar.txt
powershell -NoProfile -File .\schedule.ps1 -Action DryRun
powershell -NoProfile -File .\schedule.ps1 -Action Register
powershell -NoProfile -File .\schedule.ps1 -Action Status
```

Task name: **Watchlist Radar Daily**, current interactive user, limited privileges. Registration
does not replace an existing task; remove it explicitly before changing its configuration. The
trigger checks every 15 minutes indefinitely. The exchange-aware collector attempts **one scan
per NYSE session at/after 10:00 America/New_York**, ending eligibility at that day's exchange
close. This is 22:00 HKT during US daylight saving and 23:00 HKT otherwise, with up to 15 minutes
trigger delay. Holidays/weekends are skipped; early closes are honored. Completed daily bars become
eligible 15 minutes after the actual exchange close. Nasdaq's forward window uses exchange sessions.
Calendar dependency: `exchange_calendars==4.13.2`; unavailable/out-of-range calendar fails explicitly.

```powershell
# Manual due check through the task; usually skips outside the session.
powershell -NoProfile -File .\schedule.ps1 -Action Run
# Explicit scan/retry now (may call paid AI); bypasses today's once-only collection guard.
C:\Python314\python.exe -B daily.py --force
# Stop recurring work.
powershell -NoProfile -File .\schedule.ps1 -Action Remove
```

Both command-line and scheduled scans share an OS lock. No source/AI retry occurs automatically
after a failed daily collection. Publication may retry on two following ticks, without recollecting
or spending on AI. `local/refresh.json` records scan and publication outcomes separately; public
`docs/status.json` carries only safe health fields, never raw exception messages. Git publication
commits only the intended page, current run and status, preserving unrelated staged changes; it
rejects unrelated unpushed commits and a diverged/non-main branch. Push success verifies the remote
ref; it does not establish completion of GitHub Pages deployment. A push outage retains the last
remote page, so local logs are authoritative for publication failures.

Both pages render before replacement. Failed collection/rendering retains the previous good page.
Failure health is published with that page when Git is available. The browser checks `status.json`
every **60 seconds**, reloads when it sees a newer successful snapshot, and displays failure or
unavailable status. It marks content stale at the next exchange session's 10:30 ET even when health
publication stops. Legacy snapshots fall back to a conservative 36-hour age threshold.
Reloading the page never triggers collection; an already open browser notices a deployed update.

News coverage distinguishes checked-empty, keyword fallback, AI-reviewed/partial, skipped and
error for each name; legacy coverage is unknown. Missing/malformed optional cards are refused.
Claims need an explicit `public` licence for public values. Licensed/unknown claims are counts only;
check measurements need explicit public provenance. Option-derived ranges require valid bid/ask
and a last-trade timestamp no older than four calendar days (a conservative check, not a live-quote
guarantee). Technical levels are converted using the latest completed-bar adjustment factor;
intraday corporate actions and provider adjustments remain a limitation.

Offline verification, without OpenD, paid AI, market publication or task registration:

```powershell
C:\Python314\python.exe -B -m pytest -q test_radar.py test_daily.py --basetemp=local/test-new-run
```

## Flags

| Flag | Source | Points |
|---|---|---|
| Earnings today to +4 sessions | Nasdaq calendar; straddle and past day-1 moves from yfinance | 3 |
| VCP coil | Admiralty VCP detector, imported unchanged from the Admiralty repo | 3 actionable, 1.5 other |
| Squeeze | 20-day Bollinger width in the narrowest 2% of 6 months | 2 |
| Material news, 48h | moomoo news search, headline keyword tags | 2, +1 if broad |
| Peer reports | a name in the same `PEERS` theme reports in the window (e.g. MU -> SNDK, WDC) | 1 |
| Moving today | OpenD: move >= 5% on >= 1.5x usual volume | 1 |
| Quiet heavy volume | last session >= 2x volume on a <= 1.5% move | 1 |
| Watchlist | `watchlist.txt` | 1 |

Weights are hand-set. The **scoreboard** on the page measures them: for every earlier run, each
name's move from its run-time price to the close 1 and 5 sessions later, and each flag's average
absolute move relative to the typical name in that run (above 1.00x = the flag finds bigger movers).
Technical flags use completed daily bars only; today's forming bar is dropped.

Each pick card shows levels: earnings range from the implied move, VCP pivot and coil low,
20-day high/low and ATR.

VCP: the Admiralty detector runs unchanged. Confirmed 2-leg bases are re-checked with its
`config.LEG_FLOOR` (every leg >= 2.5 ATR at base start); failures earn no points, per the 2 Oct 2026
matched-control study. Pick cards show that study's runner exit: stop at coil low, 3R arms a
trailing stop.

## Street Validator cards

Cards from `../Equity Filings RAG/data/validation/<TICKER>.json` (spec v2.2 §9) are shown for any
ticker in the universe. Unknown `schema` versions are refused. Claims from licensed sources (broker
notes) appear only on `local/index.html` (git-ignored); `docs/` and `runs/` carry their verdict
counts only.

## News check

Headlines are dropped by keyword first (law-firm ads, market wraps). If `DEEPSEEK_API_KEY` is set
(environment or a git-ignored `.env` in this folder), one DeepSeek call per ticker then drops
headlines not about the company or not material, re-tags the rest, and writes a one-line summary.
Without a key, keyword tags are used.

## TradingView handoff

Pick cards link to daily candles for a YTD overview and configurable 15/5/1-minute candles for
single-day timing. Choose the YTD or 1D visible range in TradingView; the links do not synchronize
your account, saved layout or built-in indicators. The initial verified exchange mappings cover
ASML, SNDK, CRWV, ADEA and AAPL. Other symbols are visibly omitted rather than assigned an exchange.

Copy or download the verified shortlist from the page. Native TXT import depends on your
TradingView plan; manual symbol addition is the fallback. To bring a local ticker list into Radar:

```powershell
C:\Python314\python.exe tradingview.py .\my-tradingview-list.txt
C:\Python314\python.exe tradingview.py .\my-tradingview-list.txt --write
```

The first command previews. The second validates, backs up the existing watchlist under ignored
`local/`, then replaces `watchlist.txt`. It accepts bare US tickers or NASDAQ/NYSE/AMEX prefixes.
It does not fetch your TradingView account. Official TradingView MCP requires Essential or above.

## Data limits

moomoo OpenD on this account: 100 stocks of price history per 30 days and no US options quotes,
so bulk daily bars and options come from Yahoo Finance (yfinance). moomoo's news API allows about
14 calls in a burst, so news calls are paced.

```
C:\Python314\python.exe -m pytest -q test_radar.py
```

Research aid only; not investment advice.
