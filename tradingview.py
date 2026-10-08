"""Free-tier chart links and a local, preview-first watchlist file bridge."""
import argparse
import datetime as dt
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlencode


# Verified against each official symbol page on 2026-10-08; imports do not extend this registry.
SYMBOLS = {ticker: f"NASDAQ:{ticker}" for ticker in ("ASML", "SNDK", "CRWV", "ADEA", "AAPL")}
SYMBOL_SOURCES = {
    ticker: f"https://www.tradingview.com/symbols/NASDAQ-{ticker}/" for ticker in SYMBOLS
}
INTERVALS = {"D", "15", "5", "1"}
TICKER = re.compile(r"[A-Z][A-Z0-9]*(?:[.-][A-Z0-9]+)?\Z")


def chart_url(ticker, interval=None):
    symbol = SYMBOLS.get(ticker)
    if symbol is None:
        return None
    query = {"symbol": symbol}
    if interval is not None:
        if interval not in INTERVALS:
            raise ValueError("Supported candle intervals: D, 15, 5, 1")
        query["interval"] = interval
    return "https://www.tradingview.com/chart/?" + urlencode(query)


def export_symbols(tickers):
    """Return TradingView TXT contents and every unmapped ticker, in input order."""
    tickers = list(dict.fromkeys(tickers))
    return (",".join(SYMBOLS[t] for t in tickers if t in SYMBOLS),
            [t for t in tickers if t not in SYMBOLS])


def parse_watchlist(text):
    """Validate US watchlist syntax; explicit prefixes are user input, not verified mappings."""
    entries = {}
    for line in text.lstrip("\ufeff").splitlines():
        if not line.strip():
            continue
        for item in line.split(","):
            item = item.strip()
            if not item:
                raise ValueError("Empty symbol between commas")
            if item.startswith("###"):
                continue
            for token in item.upper().split():
                parts = token.split(":")
                exchange, ticker = (None, parts[0]) if len(parts) == 1 else (parts[0], parts[-1])
                if (len(parts) > 2 or exchange not in (None, "NASDAQ", "NYSE", "AMEX")
                        or len(ticker) > 15 or not TICKER.fullmatch(ticker)):
                    raise ValueError(f"Unsupported US symbol: {token}")
                previous = entries.get(ticker)
                verified = SYMBOLS.get(ticker)
                if exchange and ((previous and previous != exchange)
                                 or (verified and verified != f"{exchange}:{ticker}")):
                    raise ValueError(f"Conflicting exchange for {ticker}")
                entries[ticker] = exchange or previous
    if not entries:
        raise ValueError("No stock symbols supplied")
    return list(entries)


def import_watchlist(source, target, write=False):
    """Preview by default; a write replaces the watchlist, preserving its original bytes."""
    source, target = Path(source), Path(target)
    tickers = parse_watchlist(source.read_text(encoding="utf-8-sig"))
    if not write:
        return tickers, None
    backup = None
    if target.exists():
        backup_dir = target.parent / "local"
        backup_dir.mkdir(exist_ok=True)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = backup_dir / f"watchlist-{stamp}.txt"
        shutil.copyfile(target, backup)
    # Stage in the target directory so replacement stays on the same filesystem.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                     prefix="watchlist-", suffix=".pending", delete=False) as handle:
        staged = Path(handle.name)
        handle.write(" ".join(tickers) + "\n")
    try:
        staged.replace(target)
    finally:
        staged.unlink(missing_ok=True)
    return tickers, backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Local TradingView TXT or bare-ticker text file")
    parser.add_argument("--write", action="store_true", help="Replace watchlist.txt after validation")
    args = parser.parse_args()
    try:
        tickers, backup = import_watchlist(args.source, Path(__file__).parent / "watchlist.txt", args.write)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Watchlist unchanged: {exc}\n")
    print(("Written" if args.write else "Preview") + f": {len(tickers)} stocks\n" + " ".join(tickers))
    if backup:
        print(f"Original saved to {backup}")
    if not args.write:
        print("Use --write to replace watchlist.txt; this does not modify TradingView.")


if __name__ == "__main__":
    main()
