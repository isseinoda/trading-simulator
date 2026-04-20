#!/usr/bin/env python3
"""
Screener Agent
銘柄スクリーニングを実行し screener_output.json に保存する。
"""

import json
import os
import sys
import random
from datetime import datetime
import yfinance as yf

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "screener_output.json")

# Simulated baseline prices (USD) for US tickers — used when live data is unavailable
_US_FALLBACK = {
    "AAPL":  {"price": 198.5,  "name": "Apple Inc",               "pe": 29.5, "forward_pe": 26.0, "revenue_growth": 0.05, "profit_margins": 0.26, "roe": 1.60, "debt_to_equity": 150.0, "market_cap": 3_000_000_000_000, "sector": "Technology"},
    "MSFT":  {"price": 415.0,  "name": "Microsoft Corp",           "pe": 34.0, "forward_pe": 30.0, "revenue_growth": 0.16, "profit_margins": 0.35, "roe": 0.38, "debt_to_equity": 40.0,  "market_cap": 3_100_000_000_000, "sector": "Technology"},
    "GOOGL": {"price": 178.0,  "name": "Alphabet Inc",             "pe": 22.0, "forward_pe": 19.0, "revenue_growth": 0.14, "profit_margins": 0.28, "roe": 0.28, "debt_to_equity": 6.0,   "market_cap": 2_200_000_000_000, "sector": "Technology"},
    "AMZN":  {"price": 210.0,  "name": "Amazon.com Inc",           "pe": 38.0, "forward_pe": 30.0, "revenue_growth": 0.11, "profit_margins": 0.09, "roe": 0.22, "debt_to_equity": 50.0,  "market_cap": 2_200_000_000_000, "sector": "Consumer Cyclical"},
    "NVDA":  {"price": 125.0,  "name": "NVIDIA Corp",              "pe": 55.0, "forward_pe": 38.0, "revenue_growth": 0.78, "profit_margins": 0.53, "roe": 1.23, "debt_to_equity": 17.0,  "market_cap": 3_050_000_000_000, "sector": "Technology"},
    "META":  {"price": 572.0,  "name": "Meta Platforms Inc",       "pe": 27.0, "forward_pe": 23.0, "revenue_growth": 0.19, "profit_margins": 0.34, "roe": 0.38, "debt_to_equity": 10.0,  "market_cap": 1_450_000_000_000, "sector": "Technology"},
    "TSLA":  {"price": 242.0,  "name": "Tesla Inc",                "pe": 60.0, "forward_pe": 45.0, "revenue_growth": 0.02, "profit_margins": 0.08, "roe": 0.11, "debt_to_equity": 14.0,  "market_cap":  780_000_000_000, "sector": "Consumer Cyclical"},
    "BRK-B": {"price": 476.0,  "name": "Berkshire Hathaway Inc B", "pe": 21.0, "forward_pe": 19.5, "revenue_growth": 0.03, "profit_margins": 0.14, "roe": 0.11, "debt_to_equity": 28.0,  "market_cap":  700_000_000_000, "sector": "Financials"},
    "JPM":   {"price": 310.3,  "name": "JPMorgan Chase & Co",      "pe": 13.5, "forward_pe": 12.5, "revenue_growth": 0.12, "profit_margins": 0.28, "roe": 0.16, "debt_to_equity": 120.0, "market_cap":  890_000_000_000, "sector": "Financials"},
    "V":     {"price": 306.0,  "name": "Visa Inc",                 "pe": 30.0, "forward_pe": 27.0, "revenue_growth": 0.10, "profit_margins": 0.53, "roe": 0.45, "debt_to_equity": 170.0, "market_cap":  630_000_000_000, "sector": "Financials"},
}

def _synthetic_us(ticker: str) -> dict | None:
    """Return simulated OHLCV-derived metrics for a US ticker when live data fails."""
    base = _US_FALLBACK.get(ticker)
    if not base:
        return None
    rng = random.Random(ticker + datetime.now().strftime("%Y%m%d"))
    price = base["price"] * (1 + rng.uniform(-0.025, 0.025))
    prev  = price * (1 + rng.uniform(-0.015, 0.015))
    ma20  = price * rng.uniform(0.97, 1.01)
    ma50  = price * rng.uniform(0.94, 1.00)
    rsi   = rng.uniform(38, 68)
    return {
        "ticker": ticker,
        "name": base["name"],
        "price": round(price, 2),
        "change_pct": round((price - prev) / prev * 100, 4),
        "ma20": round(ma20, 2),
        "ma50": round(ma50, 2),
        "rsi": round(rsi, 1),
        "pe": base["pe"],
        "forward_pe": base["forward_pe"],
        "revenue_growth": base["revenue_growth"],
        "profit_margins": base["profit_margins"],
        "roe": base["roe"],
        "debt_to_equity": base["debt_to_equity"],
        "market_cap": base["market_cap"],
        "sector": base["sector"],
        "news": [],
        "_simulated": True,
    }


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
        print(f"  ⚠ {ticker}: {e} — trying fallback", file=sys.stderr)
        return _synthetic_us(ticker)


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
