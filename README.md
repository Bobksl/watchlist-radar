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
| Moving today | OpenD: move >= 5% on >= 1.5x usual volume | 1 |
| Quiet heavy volume | last session >= 2x volume on a <= 1.5% move | 1 |
| Watchlist | `watchlist.txt` | 1 |

Weights are hand-set; v2 replaces them with each flag's measured effect on next-5-day moves.
Technical flags use completed daily bars only; today's forming bar is dropped.

## Data limits

moomoo OpenD on this account: 100 stocks of price history per 30 days and no US options quotes,
so bulk daily bars and options come from Yahoo Finance (yfinance). moomoo's news API allows about
14 calls in a burst, so news calls are paced.

```
C:\Python314\python.exe -m pytest -q test_radar.py
```

Research aid only; not investment advice.
