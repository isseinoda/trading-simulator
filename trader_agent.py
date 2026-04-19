#!/usr/bin/env python3
"""
Trader Agent
analyst_output.json を読み込み、売買を実行して portfolio.json を更新する。
"""

import json
import os
import sys
from datetime import datetime

import portfolio as port

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ANALYST_FILE = os.path.join(BASE_DIR, "analyst_output.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
TRADE_LOG_FILE = os.path.join(BASE_DIR, "trade_log.json")


def load_analyst() -> dict:
    with open(ANALYST_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_config() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def main():
    config = load_config()
    analyst = load_analyst()
    pf = port.load(config["initial_cash"])

    per_trade = config["per_trade_amount"]
    trades_per_day = config.get("trades_per_day", 1)
    executed = []
    trades_left = trades_per_day

    # ── 売り（損切り・利確）を最優先 ─────────
    for stock in analyst.get("sell_targets", []):
        if trades_left <= 0:
            break
        ticker = stock["ticker"]
        price = stock["price"]

        if ticker in pf.get("positions", {}):
            result = port.sell(pf, ticker, price)
            if result["ok"]:
                executed.append({
                    "action": "SELL",
                    "ticker": ticker,
                    "name": stock["name"],
                    "price": price,
                    "reason": stock.get("held_reason", ""),
                    "gain": result.get("gain", 0),
                    "gain_pct": result.get("gain_pct", 0),
                    "executed_at": datetime.now().isoformat(),
                })
                print(f"  🔴 SELL {ticker} @ ¥{price:,.1f} | {stock.get('held_reason','')}")
                trades_left -= 1

    # ── 買い ─────────────────────────────
    held_tickers = set(pf.get("positions", {}).keys())
    for stock in analyst.get("buy_candidates", []):
        if trades_left <= 0:
            break
        ticker = stock["ticker"]
        price = stock["price"]

        if ticker in held_tickers:
            continue

        shares = int(per_trade / price)
        if shares <= 0 or pf["cash"] < shares * price:
            print(f"  ⚠ {ticker}: 資金不足（必要: ¥{shares*price:,.0f} / 残高: ¥{pf['cash']:,.0f}）")
            continue

        result = port.buy(pf, ticker, shares, price)
        if result["ok"]:
            executed.append({
                "action": "BUY",
                "ticker": ticker,
                "name": stock["name"],
                "price": price,
                "shares": shares,
                "amount": shares * price,
                "reason": ", ".join(stock.get("signals", [])[:3]),
                "score": stock.get("score", 0),
                "executed_at": datetime.now().isoformat(),
            })
            print(f"  🟢 BUY  {ticker} {shares}株 @ ¥{price:,.1f} | スコア:{stock.get('score',0)}")
            trades_left -= 1

    port.save(pf)

    # 取引ログを保存
    log = []
    if os.path.exists(TRADE_LOG_FILE):
        with open(TRADE_LOG_FILE, encoding="utf-8") as f:
            log = json.load(f)
    log = (executed + log)[:200]  # 直近200件
    with open(TRADE_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    if not executed:
        print("  ℹ️  本日の取引: なし（シグナル未達またはポジション制限）")

    print(f"\n✅ 取引完了。実行: {len(executed)}件 / 残高: ¥{pf['cash']:,.0f}")
    return executed


if __name__ == "__main__":
    main()
