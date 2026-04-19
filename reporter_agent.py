#!/usr/bin/env python3
"""
Reporter Agent
portfolio.json・analyst_output.json・trade_log.json を読み込み
Slack にレポートを送信する。
"""

import json
import os
import sys
import requests
from datetime import datetime
import yfinance as yf

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE = os.path.join(BASE_DIR, "portfolio.json")
ANALYST_FILE   = os.path.join(BASE_DIR, "analyst_output.json")
TRADE_LOG_FILE = os.path.join(BASE_DIR, "trade_log.json")
CONFIG_FILE    = os.path.join(BASE_DIR, "config.json")


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_current_prices(tickers: list) -> dict:
    prices = {}
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period="2d")
            if not hist.empty:
                prices[ticker] = float(hist["Close"].iloc[-1])
        except Exception:
            pass
    return prices


def build_slack_report(portfolio, analyst, trade_log, config) -> str:
    now = datetime.now().strftime("%Y/%m/%d %H:%M")
    initial = config["initial_cash"]
    market = analyst.get("market", "all") if analyst else "all"
    market_label = {"japan": "🇯🇵 日本株", "us": "🇺🇸 米国株", "all": "🌏 全市場"}.get(market, market)

    # 現在価格を取得
    held = list(portfolio.get("positions", {}).keys())
    prices = get_current_prices(held)

    total = portfolio["cash"]
    for ticker, pos in portfolio.get("positions", {}).items():
        total += prices.get(ticker, pos["avg_price"]) * pos["shares"]

    gain = total - initial
    gain_pct = gain / initial * 100
    gain_emoji = "📈" if gain >= 0 else "📉"

    lines = [
        f"*🤖 トレーディングシミュレーター レポート*",
        f"_{market_label} セッション | {now}_",
        "",
        f"*💰 ポートフォリオ*",
        f"　総資産: *¥{total:,.0f}*　{gain_emoji} {'+' if gain>=0 else ''}{gain_pct:.2f}%（{'+' if gain>=0 else ''}¥{gain:,.0f}）",
        f"　現金: ¥{portfolio['cash']:,.0f}　保有銘柄: {len(held)}銘柄",
    ]

    # 本日の取引
    today = datetime.now().strftime("%Y-%m-%d")
    today_trades = [t for t in (trade_log or []) if t.get("executed_at", "").startswith(today)]

    if today_trades:
        lines += ["", "*📋 本日の取引*"]
        for t in today_trades:
            if t["action"] == "BUY":
                lines.append(f"　🟢 BUY  {t['ticker']} {t.get('shares','')}株 @ ¥{float(t['price']):,.1f}　_{t.get('reason','')}_")
            else:
                gain_str = f"+¥{t['gain']:,.0f}" if t.get('gain',0) >= 0 else f"-¥{abs(t.get('gain',0)):,.0f}"
                lines.append(f"　🔴 SELL {t['ticker']} @ ¥{float(t['price']):,.1f}　{gain_str}（{t.get('gain_pct',0):+.1f}%）　_{t.get('reason','')}_")
    else:
        lines += ["", "*📋 本日の取引*: シグナルなし"]

    # 保有銘柄
    if held:
        lines += ["", "*📊 保有銘柄*"]
        for ticker, pos in portfolio["positions"].items():
            price = prices.get(ticker, pos["avg_price"])
            g_pct = (price - pos["avg_price"]) / pos["avg_price"] * 100
            emoji = "📈" if g_pct >= 0 else "📉"
            lines.append(f"　{emoji} {ticker}: {pos['shares']}株　取得¥{pos['avg_price']:,.0f} → 現在¥{price:,.0f}　({'+' if g_pct>=0 else ''}{g_pct:.1f}%)")

    # 注目銘柄
    if analyst:
        top_buys = analyst.get("buy_candidates", [])[:3]
        if top_buys:
            lines += ["", "*🔍 買いシグナル上位*"]
            for s in top_buys:
                sigs = ", ".join(s.get("signals", [])[:2])
                lines.append(f"　🟢 {s['ticker']}（{s['name']}） スコア:{s['score']}　_{sigs}_")

    lines += ["", "_※シミュレーション。実際の売買ではありません。_"]
    return "\n".join(lines)


def send_slack(text: str, webhook_url: str) -> bool:
    if not webhook_url:
        return False
    try:
        resp = requests.post(webhook_url, json={"text": text}, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"Slack送信エラー: {e}", file=sys.stderr)
        return False


def main(slack_webhook: str = None):
    config = load_json(CONFIG_FILE, {})
    portfolio = load_json(PORTFOLIO_FILE, {"cash": config.get("initial_cash", 1000000), "positions": {}})
    analyst = load_json(ANALYST_FILE)
    trade_log = load_json(TRADE_LOG_FILE, [])

    report = build_slack_report(portfolio, analyst, trade_log, config)
    print(report)
    print()

    webhook = slack_webhook or config.get("slack_webhook_url", "")
    if webhook:
        ok = send_slack(report, webhook)
        print("✅ Slack送信完了" if ok else "⚠️ Slack送信失敗")
    else:
        print("💡 Slackに送るには config.json の slack_webhook_url を設定してください")

    return report


if __name__ == "__main__":
    webhook = sys.argv[1] if len(sys.argv) > 1 else None
    main(webhook)
