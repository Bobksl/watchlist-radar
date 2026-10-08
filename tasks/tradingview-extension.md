# TradingView handoff — approved 8 October 2026

User uses the free plan, YTD overview and a single-day view for timing; mainly built-in indicators. YTD is a visible range, not candle interval. Initial scope is a free-account-compatible chart handoff and local file bridge. No account writes, subscription purchase, MCP connection or webhook receiver.

## Small release

- Verify five pilot exchange-qualified symbols: ASML, SNDK, CRWV, ADEA, AAPL. Unknown mappings remain visibly unavailable and are excluded with a count from exports, never assigned a guessed exchange.
- Add daily and intraday chart links on picks; verified ticker links in tables. Daily link uses daily candles; user selects YTD in TradingView. Intraday selector offers 15m, 5m and 1m; user selects the one-day visible range. Neither link promises personal-layout or indicator synchronization.
- Copy/download a verified shortlist; native TradingView TXT import depends on account feature availability. Manual symbol addition remains the free-account fallback.
- Provide preview-first local import of pasted/file tickers into Radar, explicit --write, validation before mutation and ignored local backup. Personal TradingView list is not fetched or published automatically.
- Preserve current scoring, source clocks, archived run JSON, private cards and refresh polling. Re-render current page without a new paid scan; preserve existing derived scoreboard presentation.

## Verification

Parser conflict/invalid-input protection, mapping refusal, incomplete-export disclosure, rendered links/escaping, all existing tests. Browser: chart destination/interval, copy/download controls, keyboard navigation, 320/768/1024/1440 widths and no console errors. Verify remote commit and Pages deployment separately.

## Deferred extensions and purpose

Implementation verification: 35 tests passed (existing Radar/daily tests plus parser and page
tests). Browser confirmed ASML daily and 5-minute chart destinations, interval switching on all
five links, copy success feedback, keyboard focus and no console warnings/errors. No document
overflow at 320/768/1024/1440 viewport widths. Download payload matches the verified shortlist;
the browser download completion event timed out, and clipboard contents could not be independently
read back. Saved preview evidence: ignored local/tradingview-preview.jpg. Current snapshot was
re-rendered without a new scan, preserving the scoreboard and archived run JSON.

Official MCP requires Essential or above, so account read/sync and technical snapshots through MCP are unavailable for this plan. Alert feedback needs supported account features and a receiver. A future custom Pine indicator should first serve one defined purpose (e.g. daily trend context or intraday timing), with explicit timeframe/bar-close rules and comparison against built-ins; no composite trading score or performance claim in this release.

Sources: https://www.tradingview.com/mcp/docs ; https://www.tradingview.com/pricing/ ; https://www.tradingview.com/support/solutions/43000487233-how-to-import-or-export-a-watchlist/
