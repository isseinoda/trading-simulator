"""
Vercel サーバーレス関数
GitHubからportfolio.jsonを取得し、yfinanceで現在価格を補完して返す。
"""

import json
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler
import urllib.request


REPO = "isseinoda/trading-simulator"


def fetch_github_json(token: str, path: str):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3.raw")
    req.add_header("User-Agent", "trading-simulator-dashboard")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def get_prices(tickers: list) -> dict:
    prices = {}
    try:
        import yfinance as yf
        for ticker in tickers:
            try:
                hist = yf.Ticker(ticker).history(period="2d")
                if not hist.empty:
                    prices[ticker] = float(hist["Close"].iloc[-1])
            except Exception:
                pass
    except Exception:
        pass
    return prices


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        token = os.environ.get("GITHUB_TOKEN", "")

        # GitHubからデータ取得
        portfolio  = fetch_github_json(token, "portfolio.json")
        trade_log  = fetch_github_json(token, "trade_log.json") or []
        config     = fetch_github_json(token, "config.json") or {}

        if not portfolio:
            self._respond({"error": "portfolio.json が取得できませんでした。GITHUB_TOKEN を確認してください。"})
            return

        initial_cash = config.get("initial_cash", 1000000)
        held_tickers = list(portfolio.get("positions", {}).keys())
        prices = get_prices(held_tickers)

        # 保有銘柄の損益計算
        positions = []
        total_market_value = 0.0

        for ticker, pos in portfolio.get("positions", {}).items():
            current_price = prices.get(ticker, pos["avg_price"])
            market_value  = current_price * pos["shares"]
            cost          = pos["invested"]
            gain          = market_value - cost
            gain_pct      = gain / cost * 100 if cost else 0
            total_market_value += market_value
            positions.append({
                "ticker":        ticker,
                "name":          ticker,
                "shares":        pos["shares"],
                "avg_price":     pos["avg_price"],
                "current_price": current_price,
                "market_value":  market_value,
                "cost":          cost,
                "gain":          gain,
                "gain_pct":      gain_pct,
            })

        positions.sort(key=lambda x: x["gain_pct"], reverse=True)

        cash        = portfolio["cash"]
        total       = cash + total_market_value
        total_gain  = total - initial_cash
        total_gain_pct = total_gain / initial_cash * 100

        self._respond({
            "updated_at": datetime.utcnow().strftime("%Y/%m/%d %H:%M UTC"),
            "summary": {
                "total_assets":   total,
                "cash":           cash,
                "market_value":   total_market_value,
                "total_gain":     total_gain,
                "total_gain_pct": total_gain_pct,
                "initial_cash":   initial_cash,
                "position_count": len(positions),
            },
            "positions": positions,
            "trades":    (trade_log or [])[:30],
        })

    def _respond(self, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # Vercelのログを抑制
