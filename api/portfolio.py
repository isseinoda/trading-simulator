from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
from datetime import datetime


REPO = "isseinoda/trading-simulator"


def github_raw(token: str, path: str):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3.raw")
    req.add_header("User-Agent", "trading-dashboard")
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def yf_price(ticker: str):
    # Yahoo Finance非公式APIで価格取得（依存なし）
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=2d"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
            closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
            closes = [c for c in closes if c is not None]
            return float(closes[-1]) if closes else None
    except Exception:
        return None


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        token = os.environ.get("GITHUB_TOKEN", "")
        portfolio = github_raw(token, "portfolio.json")
        trade_log = github_raw(token, "trade_log.json") or []
        config    = github_raw(token, "config.json") or {}

        if not portfolio:
            self._json({"error": "データ取得失敗。GITHUB_TOKENを確認してください。"})
            return

        initial_cash = config.get("initial_cash", 1000000)
        positions = []
        total_mv = 0.0

        for ticker, pos in portfolio.get("positions", {}).items():
            price = yf_price(ticker) or pos["avg_price"]
            mv    = price * pos["shares"]
            cost  = pos["invested"]
            gain  = mv - cost
            total_mv += mv
            positions.append({
                "ticker":        ticker,
                "name":          ticker,
                "shares":        pos["shares"],
                "avg_price":     pos["avg_price"],
                "current_price": price,
                "market_value":  mv,
                "cost":          cost,
                "gain":          gain,
                "gain_pct":      gain / cost * 100 if cost else 0,
            })

        positions.sort(key=lambda x: x["gain_pct"], reverse=True)
        cash   = portfolio["cash"]
        total  = cash + total_mv
        gain   = total - initial_cash

        self._json({
            "updated_at": datetime.utcnow().strftime("%Y/%m/%d %H:%M UTC"),
            "summary": {
                "total_assets":   total,
                "cash":           cash,
                "market_value":   total_mv,
                "total_gain":     gain,
                "total_gain_pct": gain / initial_cash * 100,
                "initial_cash":   initial_cash,
                "position_count": len(positions),
            },
            "positions": positions,
            "trades":    list(trade_log)[:30],
        })

    def _json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
