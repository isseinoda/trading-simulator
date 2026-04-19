import json
import csv
import os
from datetime import datetime

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "portfolio.json")
TRADES_FILE = os.path.join(os.path.dirname(__file__), "trades.csv")


def load(initial_cash: float) -> dict:
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, encoding="utf-8") as f:
            return json.load(f)
    portfolio = {
        "cash": initial_cash,
        "positions": {},
        "created_at": datetime.now().isoformat(),
    }
    save(portfolio)
    return portfolio


def save(portfolio: dict):
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(portfolio, f, ensure_ascii=False, indent=2)


def buy(portfolio: dict, ticker: str, shares: int, price: float) -> dict:
    amount = shares * price
    if portfolio["cash"] < amount:
        return {"ok": False, "reason": "資金不足"}

    pos = portfolio["positions"].get(ticker, {"shares": 0, "avg_price": 0.0, "invested": 0.0})
    total_shares = pos["shares"] + shares
    total_invested = pos["invested"] + amount
    portfolio["positions"][ticker] = {
        "shares": total_shares,
        "avg_price": total_invested / total_shares,
        "invested": total_invested,
        "bought_at": datetime.now().isoformat(),
    }
    portfolio["cash"] -= amount
    _log_trade("BUY", ticker, shares, price)
    return {"ok": True}


def sell(portfolio: dict, ticker: str, price: float) -> dict:
    if ticker not in portfolio["positions"]:
        return {"ok": False, "reason": "保有していない"}

    pos = portfolio["positions"].pop(ticker)
    proceeds = pos["shares"] * price
    portfolio["cash"] += proceeds
    gain = proceeds - pos["invested"]
    gain_pct = gain / pos["invested"] * 100
    _log_trade("SELL", ticker, pos["shares"], price, gain, gain_pct)
    return {"ok": True, "gain": gain, "gain_pct": gain_pct}


def current_value(portfolio: dict, prices: dict) -> float:
    total = portfolio["cash"]
    for ticker, pos in portfolio["positions"].items():
        price = prices.get(ticker, pos["avg_price"])
        total += price * pos["shares"]
    return total


def _log_trade(action: str, ticker: str, shares: int, price: float, gain: float = 0.0, gain_pct: float = 0.0):
    write_header = not os.path.exists(TRADES_FILE)
    with open(TRADES_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["datetime", "action", "ticker", "shares", "price", "gain", "gain_pct"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            action, ticker, shares, f"{price:.2f}",
            f"{gain:.0f}", f"{gain_pct:.2f}",
        ])
