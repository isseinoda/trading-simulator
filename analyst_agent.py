#!/usr/bin/env python3
"""
Analyst Agent
screener_output.json を読み込み、各銘柄にスコアと売買シグナルを付けて
analyst_output.json に保存する。
"""

import json
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCREENER_FILE = os.path.join(BASE_DIR, "screener_output.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "analyst_output.json")
PORTFOLIO_FILE = os.path.join(BASE_DIR, "portfolio.json")


def load_screener() -> dict:
    with open(SCREENER_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_portfolio() -> dict:
    if not os.path.exists(PORTFOLIO_FILE):
        return {"cash": 1000000, "positions": {}}
    with open(PORTFOLIO_FILE, encoding="utf-8") as f:
        return json.load(f)


def score_stock(stock: dict, portfolio: dict) -> dict:
    score = 0
    signals = []

    # ── ファンダメンタル分析 ──────────────────
    pe = stock.get("pe")
    if pe:
        if 0 < pe < 15:
            score += 3; signals.append(f"PER割安({pe:.1f})")
        elif pe < 25:
            score += 1; signals.append(f"PER適正({pe:.1f})")
        elif pe > 50:
            score -= 2; signals.append(f"PER割高({pe:.1f})")

    rev_growth = stock.get("revenue_growth")
    if rev_growth is not None:
        if rev_growth > 0.20:
            score += 3; signals.append(f"売上高成長+{rev_growth*100:.0f}%")
        elif rev_growth > 0.10:
            score += 2; signals.append(f"売上成長+{rev_growth*100:.0f}%")
        elif rev_growth < 0:
            score -= 2; signals.append(f"売上減少{rev_growth*100:.0f}%")

    margin = stock.get("profit_margins")
    if margin and margin > 0.20:
        score += 2; signals.append(f"高利益率{margin*100:.0f}%")
    elif margin and margin > 0.10:
        score += 1; signals.append(f"利益率{margin*100:.0f}%")

    roe = stock.get("roe")
    if roe and roe > 0.20:
        score += 2; signals.append(f"高ROE{roe*100:.0f}%")
    elif roe and roe > 0.10:
        score += 1

    # ── テクニカル分析 ──────────────────────
    ma20 = stock.get("ma20", 0)
    ma50 = stock.get("ma50", 0)
    if ma20 and ma50:
        if ma20 > ma50:
            score += 1; signals.append("MA20>MA50(上昇)")
        else:
            score -= 1; signals.append("MA20<MA50(下降)")

    rsi = stock.get("rsi", 50)
    if rsi < 30:
        score += 2; signals.append(f"RSI売られ過ぎ({rsi:.0f})")
    elif rsi < 40:
        score += 1; signals.append(f"RSI低め({rsi:.0f})")
    elif rsi > 75:
        score -= 2; signals.append(f"RSI買われ過ぎ({rsi:.0f})")

    # ── ニュース簡易スコア ───────────────────
    positive_kw = ["beat", "surge", "record", "growth", "profit", "raises", "上昇", "好調", "増益", "最高", "増収"]
    negative_kw = ["miss", "drop", "loss", "cut", "warn", "fraud", "下落", "不振", "減益", "赤字", "違反"]
    for headline in stock.get("news", []):
        h = headline.lower()
        if any(k in h for k in positive_kw):
            score += 1
        if any(k in h for k in negative_kw):
            score -= 1

    # ── 損切り・利確チェック（既保有銘柄） ────
    ticker = stock["ticker"]
    action = "HOLD"
    held_reason = None

    if ticker in portfolio.get("positions", {}):
        pos = portfolio["positions"][ticker]
        gain_pct = (stock["price"] - pos["avg_price"]) / pos["avg_price"]
        if gain_pct <= -0.05:
            action = "SELL"
            held_reason = f"損切りライン到達({gain_pct*100:.1f}%)"
        elif gain_pct >= 0.15:
            action = "SELL"
            held_reason = f"利確ライン到達({gain_pct*100:.1f}%)"
        else:
            action = "HOLD"
            held_reason = f"保有中({gain_pct*100:+.1f}%)"
    else:
        if score >= 5:
            action = "BUY"
        elif score >= 3:
            action = "WATCH"
        else:
            action = "SKIP"

    return {
        **stock,
        "score": score,
        "signals": signals,
        "action": action,
        "held_reason": held_reason,
    }


def main():
    screener = load_screener()
    portfolio = load_portfolio()

    print(f"🔍 {len(screener['stocks'])}銘柄を分析中...")
    analyzed = [score_stock(s, portfolio) for s in screener["stocks"]]
    analyzed.sort(key=lambda x: x["score"], reverse=True)

    buy_candidates = [s for s in analyzed if s["action"] == "BUY"]
    sell_targets   = [s for s in analyzed if s["action"] == "SELL"]
    watch_list     = [s for s in analyzed if s["action"] == "WATCH"]

    print(f"\n  📈 買いシグナル: {len(buy_candidates)}銘柄")
    for s in buy_candidates:
        print(f"     → {s['ticker']} ({s['name']}) スコア:{s['score']} | {', '.join(s['signals'][:3])}")

    print(f"  📉 売りシグナル: {len(sell_targets)}銘柄")
    for s in sell_targets:
        print(f"     → {s['ticker']} | {s.get('held_reason','')}")

    output = {
        "run_at": datetime.now().isoformat(),
        "market": screener["market"],
        "buy_candidates": buy_candidates[:5],
        "sell_targets": sell_targets,
        "watch_list": watch_list[:5],
        "all_stocks": analyzed,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 分析結果を {OUTPUT_FILE} に保存しました")
    return output


if __name__ == "__main__":
    main()
