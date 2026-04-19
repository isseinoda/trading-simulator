#!/usr/bin/env python3
"""
トレーディングシミュレーター
実際の証券口座を使わずに株式売買をシミュレートします。
"""

import json
import os
import sys
import yfinance as yf

import portfolio as port
import screener
import reporter

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")


def load_config() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def get_current_prices(tickers: list[str]) -> dict:
    prices = {}
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period="1d")
            if not hist.empty:
                prices[ticker] = float(hist["Close"].iloc[-1])
        except Exception:
            pass
    return prices


def check_stop_loss_and_take_profit(portfolio: dict, prices: dict, config: dict) -> list[dict]:
    signals = []
    for ticker, pos in list(portfolio["positions"].items()):
        price = prices.get(ticker)
        if not price:
            continue
        gain_pct = (price - pos["avg_price"]) / pos["avg_price"]
        if gain_pct <= config["stop_loss"]:
            signals.append({
                "action": "SELL",
                "ticker": ticker,
                "name": ticker,
                "price": price,
                "shares": pos["shares"],
                "reason": f"損切り ({gain_pct*100:.1f}%)",
                "priority": 0,
            })
        elif gain_pct >= config["take_profit"]:
            signals.append({
                "action": "SELL",
                "ticker": ticker,
                "name": ticker,
                "price": price,
                "shares": pos["shares"],
                "reason": f"利確 ({gain_pct*100:.1f}%)",
                "priority": 0,
            })
    return signals


def main():
    config = load_config()
    pf = port.load(config["initial_cash"])

    all_tickers = config["watchlist"]["japan"] + config["watchlist"]["us"]

    print("📡 市場データを取得中...")
    candidates = screener.analyze(all_tickers)
    prices = {c.ticker: c.price for c in candidates}

    # 損切り・利確チェック（最優先）
    exit_signals = check_stop_loss_and_take_profit(pf, prices, config)

    # 新規買いシグナル
    buy_signals = []
    held_tickers = set(pf["positions"].keys())
    for c in candidates:
        if c.action == "BUY" and c.ticker not in held_tickers:
            shares = int(config["per_trade_amount"] / c.price)
            if shares > 0 and pf["cash"] >= shares * c.price:
                buy_signals.append({
                    "action": "BUY",
                    "ticker": c.ticker,
                    "name": c.name,
                    "price": c.price,
                    "shares": shares,
                    "reason": ", ".join(c.reasons[:3]) or "スコア基準達成",
                })

    # 1日の取引上限: まず損切り・利確を優先、残枠で買い
    executed = []
    trades_left = config["trades_per_day"]

    for sig in exit_signals:
        if trades_left <= 0:
            break
        result = port.sell(pf, sig["ticker"], sig["price"])
        if result["ok"]:
            sig["name"] = sig["ticker"]
            executed.append(sig)
            trades_left -= 1

    for sig in buy_signals:
        if trades_left <= 0:
            break
        result = port.buy(pf, sig["ticker"], sig["shares"], sig["price"])
        if result["ok"]:
            executed.append(sig)
            trades_left -= 1

    port.save(pf)

    report = reporter.build_report(pf, executed, candidates, prices, config["initial_cash"])
    reporter.print_report(report)

    if config.get("slack_webhook_url"):
        sent = reporter.send_slack(report, config["slack_webhook_url"])
        print("✅ Slack送信完了" if sent else "⚠ Slack送信失敗")
    else:
        print("💡 Slackに送るには config.json の slack_webhook_url を設定してください")


if __name__ == "__main__":
    main()
