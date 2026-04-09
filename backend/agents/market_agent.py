"""
FinAgentX – Market Intelligence Agent
Fetches price, volume, sentiment, RSI from Binance/CoinGecko.
Falls back to realistic mock data if USE_MOCK_DATA=true or APIs fail.
"""
import random
import math
import httpx
from typing import List, Dict
from datetime import datetime

from .base_agent import BaseAgent
from backend.config import (
    USE_MOCK_DATA, BINANCE_API_KEY, COINGECKO_API_KEY
)
from backend.models import MarketData


# Symbols we track by default
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "HSKUSDT"]


class MarketIntelligenceAgent(BaseAgent):
    name = "MarketIntelligenceAgent"

    # ── Public interface ──────────────────────────────────────────────────────

    async def run(self, symbols: List[str] = None) -> List[MarketData]:
        """
        Fetch market data for given symbols.
        Returns a list of MarketData objects.
        Decision is logged into shared memory.
        """
        symbols = symbols or DEFAULT_SYMBOLS

        if USE_MOCK_DATA:
            data = self._mock_market_data(symbols)
        else:
            data = await self._fetch_binance(symbols)
            if not data:
                data = await self._fetch_coingecko(symbols)
            if not data:
                data = self._mock_market_data(symbols)

        # Enrich with computed indicators
        for d in data:
            d.sentiment = self._compute_sentiment(d)
            d.trend     = self._compute_trend(d)
            d.rsi       = self._compute_rsi(d)

        # Log decision to shared memory
        summary = [{"symbol": d.symbol, "price": d.price, "change": d.change_24h} for d in data]
        self.log("market_scan", summary, f"Scanned {len(data)} symbols at {datetime.utcnow().isoformat()}")

        return data

    # ── Data sources ──────────────────────────────────────────────────────────

    async def _fetch_binance(self, symbols: List[str]) -> List[MarketData]:
        """Fetch 24-hour ticker stats from Binance public API."""
        results = []
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                for symbol in symbols:
                    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        t = resp.json()
                        results.append(MarketData(
                            symbol=symbol,
                            price=float(t["lastPrice"]),
                            change_24h=float(t["priceChangePercent"]),
                            volume_24h=float(t["quoteVolume"]),
                        ))
        except Exception as e:
            self.logger.warning(f"Binance fetch failed: {e}")
        return results

    async def _fetch_coingecko(self, symbols: List[str]) -> List[MarketData]:
        """Fallback: CoinGecko simple price API."""
        coin_map = {
            "BTCUSDT": "bitcoin", "ETHUSDT": "ethereum",
            "BNBUSDT": "binancecoin", "SOLUSDT": "solana",
        }
        results = []
        try:
            ids = ",".join(coin_map.get(s, s.replace("USDT", "").lower()) for s in symbols)
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true"
            headers = {"x-cg-demo-api-key": COINGECKO_API_KEY} if COINGECKO_API_KEY else {}
            async with httpx.AsyncClient(timeout=10, headers=headers) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    for symbol in symbols:
                        cid = coin_map.get(symbol, symbol.replace("USDT", "").lower())
                        if cid in data:
                            d = data[cid]
                            results.append(MarketData(
                                symbol=symbol,
                                price=d.get("usd", 0),
                                change_24h=d.get("usd_24h_change", 0),
                                volume_24h=d.get("usd_24h_vol", 0),
                            ))
        except Exception as e:
            self.logger.warning(f"CoinGecko fetch failed: {e}")
        return results

    def _mock_market_data(self, symbols: List[str]) -> List[MarketData]:
        """
        Realistic mock data with slight randomization around base prices.
        Used in demo mode so the system always works without API keys.
        """
        base_prices = {
            "BTCUSDT": 68_000, "ETHUSDT": 3_500, "BNBUSDT": 580,
            "SOLUSDT": 175, "HSKUSDT": 0.85, "ADAUSDT": 0.45,
            "DOGEUSDT": 0.18, "MATICUSDT": 0.92,
        }
        results = []
        for symbol in symbols:
            base   = base_prices.get(symbol, 1.0)
            noise  = random.uniform(-0.04, 0.04)          # ±4% random movement
            price  = round(base * (1 + noise), 4)
            change = round(random.gauss(0.5, 3.0), 2)     # realistic daily change
            volume = round(base * random.uniform(1_000, 50_000), 0)
            results.append(MarketData(
                symbol=symbol,
                price=price,
                change_24h=change,
                volume_24h=volume,
                market_cap=round(price * random.uniform(1e7, 1e10), 0),
            ))
        return results

    # ── Computed indicators ───────────────────────────────────────────────────

    def _compute_sentiment(self, d: MarketData) -> str:
        if d.change_24h > 3:  return "bullish"
        if d.change_24h < -3: return "bearish"
        return "neutral"

    def _compute_trend(self, d: MarketData) -> str:
        if d.change_24h > 1:   return "up"
        if d.change_24h < -1:  return "down"
        return "sideways"

    def _compute_rsi(self, d: MarketData) -> float:
        """
        Simplified RSI approximation from 24h change (real impl needs OHLCV history).
        For demo: map price change to RSI range 20-80.
        """
        change_clamped = max(-10, min(10, d.change_24h))
        rsi = 50 + (change_clamped * 3)                   # 20–80 range
        return round(rsi, 1)
