import yfinance as yf
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StockSignal:
    ticker: str
    name: str
    price: float
    score: int
    reasons: list[str] = field(default_factory=list)
    news_headlines: list[str] = field(default_factory=list)
    pe: Optional[float] = None
    revenue_growth: Optional[float] = None
    action: str = "HOLD"  # BUY / SELL / HOLD


def _score_fundamental(info: dict) -> tuple[int, list[str]]:
    score = 0
    reasons = []

    pe = info.get("trailingPE")
    if pe and 0 < pe < 20:
        score += 2
        reasons.append(f"PER低({pe:.1f})")
    elif pe and pe > 50:
        score -= 1
        reasons.append(f"PER高({pe:.1f})")

    rev_growth = info.get("revenueGrowth")
    if rev_growth and rev_growth > 0.10:
        score += 2
        reasons.append(f"売上成長+{rev_growth*100:.0f}%")
    elif rev_growth and rev_growth < 0:
        score -= 1
        reasons.append(f"売上減少{rev_growth*100:.0f}%")

    profit_margin = info.get("profitMargins")
    if profit_margin and profit_margin > 0.15:
        score += 1
        reasons.append(f"利益率{profit_margin*100:.0f}%")

    roe = info.get("returnOnEquity")
    if roe and roe > 0.15:
        score += 1
        reasons.append(f"ROE{roe*100:.0f}%")

    return score, reasons


def _score_technical(hist: pd.DataFrame) -> tuple[int, list[str]]:
    score = 0
    reasons = []
    closes = hist["Close"]

    if len(closes) >= 50:
        ma20 = closes.tail(20).mean()
        ma50 = closes.tail(50).mean()
        if ma20 > ma50:
            score += 1
            reasons.append("MA20↑MA50")
        else:
            score -= 1
            reasons.append("MA20↓MA50")

    if len(closes) >= 14:
        delta = closes.diff()
        gain = delta.clip(lower=0).tail(14).mean()
        loss = (-delta.clip(upper=0)).tail(14).mean()
        if loss > 0:
            rsi = 100 - (100 / (1 + gain / loss))
            if rsi < 35:
                score += 1
                reasons.append(f"RSI売られ過ぎ({rsi:.0f})")
            elif rsi > 70:
                score -= 1
                reasons.append(f"RSI買われ過ぎ({rsi:.0f})")

    return score, reasons


def _score_news(news: list) -> tuple[int, list[str]]:
    score = 0
    headlines = []
    positive_kw = ["beat", "surge", "record", "growth", "profit", "raises", "上昇", "好調", "増益", "最高"]
    negative_kw = ["miss", "drop", "loss", "cut", "warn", "下落", "不振", "減益", "赤字"]

    for item in news[:5]:
        title = item.get("title", "")
        if not title:
            continue
        headlines.append(title)
        title_lower = title.lower()
        if any(kw in title_lower for kw in positive_kw):
            score += 1
        if any(kw in title_lower for kw in negative_kw):
            score -= 1

    return score, headlines


def analyze(tickers: list[str]) -> list[StockSignal]:
    results = []
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            hist = stock.history(period="3mo")
            if hist.empty or "Close" not in hist:
                continue

            price = float(hist["Close"].iloc[-1])
            name = info.get("shortName") or info.get("longName") or ticker

            f_score, f_reasons = _score_fundamental(info)
            t_score, t_reasons = _score_technical(hist)
            n_score, headlines = _score_news(stock.news or [])

            total = f_score + t_score + n_score
            all_reasons = f_reasons + t_reasons

            action = "HOLD"
            if total >= 4:
                action = "BUY"
            elif total <= -2:
                action = "SELL_SIGNAL"

            results.append(StockSignal(
                ticker=ticker,
                name=name,
                price=price,
                score=total,
                reasons=all_reasons,
                news_headlines=headlines[:3],
                pe=info.get("trailingPE"),
                revenue_growth=info.get("revenueGrowth"),
                action=action,
            ))
        except Exception as e:
            print(f"  ⚠ {ticker} スキップ: {e}")

    return sorted(results, key=lambda x: x.score, reverse=True)
