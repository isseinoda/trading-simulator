import json
import requests
from datetime import datetime


def build_report(portfolio: dict, executed: list, candidates: list, prices: dict, initial_cash: float) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = portfolio["cash"]
    for ticker, pos in portfolio["positions"].items():
        total += prices.get(ticker, pos["avg_price"]) * pos["shares"]

    gain_total = total - initial_cash
    gain_pct = gain_total / initial_cash * 100

    lines = [
        f"📊 *トレーディングシミュレーター* ({now})",
        "",
        f"💰 *ポートフォリオ*",
        f"  現金: ¥{portfolio['cash']:,.0f}",
        f"  総資産: ¥{total:,.0f}  ({gain_pct:+.2f}%)",
        "",
    ]

    if executed:
        lines.append("✅ *本日の取引*")
        for t in executed:
            emoji = "🟢" if t["action"] == "BUY" else "🔴"
            lines.append(f"  {emoji} {t['action']} {t['name']}({t['ticker']})  {t['shares']}株 @ ¥{t['price']:,.0f}")
            lines.append(f"     理由: {t['reason']}")
    else:
        lines.append("📭 *本日の取引*: シグナルなし / 条件未達")

    if portfolio["positions"]:
        lines.append("")
        lines.append("📈 *保有銘柄*")
        for ticker, pos in portfolio["positions"].items():
            price = prices.get(ticker, pos["avg_price"])
            gain_pct_pos = (price - pos["avg_price"]) / pos["avg_price"] * 100
            emoji = "📈" if gain_pct_pos >= 0 else "📉"
            lines.append(f"  {emoji} {ticker}: {pos['shares']}株  取得¥{pos['avg_price']:,.0f} → 現在¥{price:,.0f} ({gain_pct_pos:+.1f}%)")

    lines.append("")
    lines.append("🔍 *スクリーニング上位3銘柄*")
    for c in candidates[:3]:
        action_emoji = "🟢" if c.action == "BUY" else ("🔴" if c.action == "SELL_SIGNAL" else "⚪")
        reason_str = ", ".join(c.reasons[:3]) if c.reasons else "シグナルなし"
        lines.append(f"  {action_emoji} {c.name}({c.ticker}) スコア:{c.score}  {reason_str}")
        if c.news_headlines:
            lines.append(f"     📰 {c.news_headlines[0][:60]}")

    return "\n".join(lines)


def send_slack(report: str, webhook_url: str) -> bool:
    if not webhook_url:
        return False
    try:
        resp = requests.post(webhook_url, json={"text": report}, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"Slack送信エラー: {e}")
        return False


def print_report(report: str):
    print("\n" + "=" * 60)
    print(report)
    print("=" * 60 + "\n")
