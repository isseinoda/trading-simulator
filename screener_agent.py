#!/usr/bin/env python3
"""
Screener Agent
銘柄スクリーニングを実行し screener_output.json に保存する。
"""

import json
import os
import sys
from datetime import datetime
import yfinance as yf

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "screener_output.json")


def load_config():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def fetch_stock_data(ticker: str) -> dict | None:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="3mo")
        if hist.empty:
            return None

        closes = hist["Close"]
        price = float(closes.iloc[-1])
        prev_price = float(closes.iloc[-2]) if len(closes) >= 2 else price
        change_pct = (price - prev_price) / prev_price * 100

        ma20 = float(closes.tail(20).mean()) if len(closes) >= 20 else price
        ma50 = float(closes.tail(50).mean()) if len(closes) >= 50 else price

        # RSI
        delta = closes.diff()
        gain = delta.clip(lower=0).tail(14).mean()
        loss = (-delta.clip(upper=0)).tail(14).mean()
        rsi = 100 - (100 / (1 + gain / loss)) if loss > 0 else 50

        # ニュース
        news = []
        for item in (stock.news or [])[:5]:
            title = item.get("title", "")
            if title:
                news.append(title)

        return {
            "ticker": ticker,
            "name": info.get("shortName") or info.get("longName") or ticker,
            "price": price,
            "change_pct": change_pct,
            "ma20": ma20,
            "ma50": ma50,
            "rsi": float(rsi),
            "pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "revenue_growth": info.get("revenueGrowth"),
            "profit_margins": info.get("profitMargins"),
            "roe": info.get("returnOnEquity"),
            "debt_to_equity": info.get("debtToEquity"),
            "market_cap": info.get("marketCap"),
            "sector": info.get("sector"),
            "news": news,
        }
    except Exception as e:
        print(f"  ⚠ {ticker}: {e}", file=sys.stderr)
        return None


def main(market: str = "all"):
    config = load_config()
    watchlist = config["watchlist"]

    if market == "japan":
        tickers = watchlist["japan"]
    elif market == "us":
        tickers = watchlist["us"]
    else:
        tickers = watchlist["japan"] + watchlist["us"]

    print(f"📡 {len(tickers)}銘柄をスクリーニング中...")
    results = []
    for ticker in tickers:
        data = fetch_stock_data(ticker)
        if data:
            results.append(data)
            print(f"  ✓ {ticker}: ¥{data['price']:,.1f} ({data['change_pct']:+.2f}%)")

    output = {
        "market": market,
        "run_at": datetime.now().isoformat(),
        "stocks": results,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(results)}銘柄のデータを {OUTPUT_FILE} に保存しました")
    return output


if __name__ == "__main__":
    market = sys.argv[1] if len(sys.argv) > 1 else "all"
    main(market)
