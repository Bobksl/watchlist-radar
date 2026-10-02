# Watchlist Radar

On-demand scan of tech, semiconductor and AI-adjacent US stocks for names likely to move in the next
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

## Data limits

moomoo OpenD on this account: 100 stocks of price history per 30 days and no US options quotes,
so bulk daily bars and options come from Yahoo Finance (yfinance). moomoo's news API allows about
14 calls in a burst, so news calls are paced.

```
C:\Python314\python.exe -m pytest -q test_radar.py
```

Research aid only; not investment advice.
