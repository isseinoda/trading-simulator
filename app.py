#!/usr/bin/env python3
"""
トレーディングシミュレーター ダッシュボード
SBI証券風UIで仮想ポートフォリオを表示します。
"""

import json
import csv
import os
from datetime import datetime
from flask import Flask, render_template, jsonify
import yfinance as yf

BASE_DIR = os.path.dirname(__file__)
PORTFOLIO_FILE = os.path.join(BASE_DIR, "portfolio.json")
TRADES_FILE = os.path.join(BASE_DIR, "trades.csv")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

app = Flask(__name__)


def load_config():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_portfolio():
    if not os.path.exists(PORTFOLIO_FILE):
        return None
    with open(PORTFOLIO_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_trades():
    if not os.path.exists(TRADES_FILE):
        return []
    trades = []
    with open(TRADES_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            trades.append(row)
    return list(reversed(trades))


def get_price(ticker: str) -> "float | None":
    try:
        hist = yf.Ticker(ticker).history(period="2d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None


def get_prices(tickers: list[str]) -> dict:
    prices = {}
    for ticker in tickers:
        p = get_price(ticker)
        if p:
            prices[ticker] = p
    return prices


def get_name(ticker: str) -> str:
    try:
        info = yf.Ticker(ticker).info
        return info.get("shortName") or info.get("longName") or ticker
    except Exception:
        return ticker


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/portfolio")
def api_portfolio():
    config = load_config()
    portfolio = load_portfolio()
    trades = load_trades()

    if not portfolio:
        return jsonify({"error": "ポートフォリオが見つかりません。simulator.py を先に実行してください。"})

    # 現在価格を取得
    held_tickers = list(portfolio.get("positions", {}).keys())
    prices = get_prices(held_tickers)

    # 保有銘柄の詳細
    positions = []
    total_market_value = 0
    total_cost = 0

    for ticker, pos in portfolio.get("positions", {}).items():
        current_price = prices.get(ticker, pos["avg_price"])
        market_value = current_price * pos["shares"]
        cost = pos["invested"]
        gain = market_value - cost
        gain_pct = gain / cost * 100

        total_market_value += market_value
        total_cost += cost

        positions.append({
            "ticker": ticker,
            "name": get_name(ticker),
            "shares": pos["shares"],
            "avg_price": pos["avg_price"],
            "current_price": current_price,
            "market_value": market_value,
            "cost": cost,
            "gain": gain,
            "gain_pct": gain_pct,
        })

    positions.sort(key=lambda x: x["gain_pct"], reverse=True)

    cash = portfolio["cash"]
    total_assets = cash + total_market_value
    initial_cash = config["initial_cash"]
    total_gain = total_assets - initial_cash
    total_gain_pct = total_gain / initial_cash * 100

    # 直近30件の取引
    recent_trades = trades[:30]

    return jsonify({
        "updated_at": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "summary": {
            "total_assets": total_assets,
            "cash": cash,
            "market_value": total_market_value,
            "total_gain": total_gain,
            "total_gain_pct": total_gain_pct,
            "initial_cash": initial_cash,
            "position_count": len(positions),
        },
        "positions": positions,
        "trades": recent_trades,
    })


if __name__ == "__main__":
    print("🚀 ダッシュボード起動中... http://localhost:5050 を開いてください")
    app.run(debug=False, port=5050)
