"""
FinAgentX – Market Intelligence Agent

Data source priority (automatic fallback chain):
  1. Binance public REST API (no key needed for price/ticker)
  2. CoinGecko Demo API  (free, 30 req/min, no key needed for basic calls)
  3. CoinGecko Pro API   (if COINGECKO_API_KEY is set)
  4. Mock data           (if USE_MOCK_DATA=true OR all APIs fail)

Binance public endpoints are unauthenticated – BINANCE_API_KEY is only needed
for private endpoints (order placement etc.) which we don't use here.
"""
import random
import math
import httpx
from typing import List, Optional
from datetime import datetime

from .base_agent import BaseAgent
from backend.config import USE_MOCK_DATA, COINGECKO_API_KEY
from backend.models import MarketData


DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "HSKUSDT"]

# CoinGecko symbol → coin-id map
CG_ID_MAP = {
    "BTCUSDT":  "bitcoin",
    "ETHUSDT":  "ethereum",
    "BNBUSDT":  "binancecoin",
    "SOLUSDT":  "solana",
    "HSKUSDT":  "hashkey-token",
    "ADAUSDT":  "cardano",
    "DOGEUSDT": "dogecoin",
    "MATICUSDT":"matic-network",
}


class MarketIntelligenceAgent(BaseAgent):
    name = "MarketIntelligenceAgent"

    async def run(self, symbols: Optional[List[str]] = None) -> List[MarketData]:
        symbols = symbols or DEFAULT_SYMBOLS

        if USE_MOCK_DATA:
            data = self._mock_market_data(symbols)
        else:
            data = await self._fetch_binance_public(symbols)
            if not data:
                data = await self._fetch_coingecko(symbols)
            if not data:
                self.logger.warning("All market APIs failed – using mock data")
                data = self._mock_market_data(symbols)

        for d in data:
            d.sentiment = self._sentiment(d)
            d.trend     = self._trend(d)
            d.rsi       = self._approx_rsi(d)

        self.log("market_scan",
                 [{"symbol": d.symbol, "price": d.price, "change": d.change_24h} for d in data],
                 f"Scanned {len(data)} symbols at {datetime.utcnow().isoformat()}")
        return data

    # ── Binance public (no API key required) ────────────────────────────────

    async def _fetch_binance_public(self, symbols: List[str]) -> List[MarketData]:
        """
        Binance 24-hr ticker – completely public, no auth needed.
        Docs: https://binance-docs.github.io/apidocs/spot/en/#24hr-ticker-price-change-statistics
        """
        results = []
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                for sym in symbols:
                    if sym == "HSKUSDT":      # not listed on Binance
                        continue
                    r = await client.get(
                        "https://api.binance.com/api/v3/ticker/24hr",
                        params={"symbol": sym}
                    )
                    if r.status_code == 200:
                        t = r.json()
                        results.append(MarketData(
                            symbol    = sym,
                            price     = float(t["lastPrice"]),
                            change_24h= float(t["priceChangePercent"]),
                            volume_24h= float(t["quoteVolume"]),
                            market_cap= None,
                        ))
        except Exception as e:
            self.logger.warning(f"Binance public fetch failed: {e}")
        return results

    # ── CoinGecko (free Demo tier, no key needed) ────────────────────────────

    async def _fetch_coingecko(self, symbols: List[str]) -> List[MarketData]:
        """
        CoinGecko simple/price endpoint.
        Free demo: 30 req/min, no key required.
        Pro: set COINGECKO_API_KEY for higher limits.
        """
        ids = ",".join(
            CG_ID_MAP.get(s, s.lower().replace("usdt", ""))
            for s in symbols
        )
        params = {
            "ids":               ids,
            "vs_currencies":     "usd",
            "include_24hr_change": "true",
            "include_24hr_vol":    "true",
            "include_market_cap":  "true",
        }
        headers = {}
        if COINGECKO_API_KEY:
            # Pro API
            base = "https://pro-api.coingecko.com/api/v3"
            headers["x-cg-pro-api-key"] = COINGECKO_API_KEY
        else:
            # Free Demo API (no key, lower rate limit)
            base = "https://api.coingecko.com/api/v3"

        results = []
        try:
            async with httpx.AsyncClient(timeout=10, headers=headers) as client:
                r = await client.get(f"{base}/simple/price", params=params)
                if r.status_code == 200:
                    raw = r.json()
                    for sym in symbols:
                        cid = CG_ID_MAP.get(sym, sym.lower().replace("usdt", ""))
                        if cid in raw:
                            d = raw[cid]
                            results.append(MarketData(
                                symbol    = sym,
                                price     = d.get("usd", 0),
                                change_24h= d.get("usd_24h_change", 0),
                                volume_24h= d.get("usd_24h_vol", 0),
                                market_cap= d.get("usd_market_cap"),
                            ))
                else:
                    self.logger.warning(f"CoinGecko HTTP {r.status_code}")
        except Exception as e:
            self.logger.warning(f"CoinGecko fetch failed: {e}")
        return results

    # ── Mock data (always works, no internet needed) ─────────────────────────

    def _mock_market_data(self, symbols: List[str]) -> List[MarketData]:
        base_prices = {
            "BTCUSDT": 68_000, "ETHUSDT": 3_500, "BNBUSDT": 580,
            "SOLUSDT": 175,    "HSKUSDT": 0.85,  "ADAUSDT": 0.45,
            "DOGEUSDT": 0.18,  "MATICUSDT": 0.92,
        }
        results = []
        for sym in symbols:
            base   = base_prices.get(sym, 1.0)
            noise  = random.uniform(-0.04, 0.04)
            price  = round(base * (1 + noise), 4)
            change = round(random.gauss(0.5, 3.0), 2)
            vol    = round(base * random.uniform(1_000, 50_000), 0)
            results.append(MarketData(
                symbol    = sym,
                price     = price,
                change_24h= change,
                volume_24h= vol,
                market_cap= round(price * random.uniform(1e7, 1e10), 0),
            ))
        return results

    # ── Indicators ────────────────────────────────────────────────────────────

    def _sentiment(self, d: MarketData) -> str:
        if d.change_24h > 3:  return "bullish"
        if d.change_24h < -3: return "bearish"
        return "neutral"

    def _trend(self, d: MarketData) -> str:
        if d.change_24h > 1:  return "up"
        if d.change_24h < -1: return "down"
        return "sideways"

    def _approx_rsi(self, d: MarketData) -> float:
        """RSI approximation from 24h change (50 ± 30 range)."""
        c = max(-10, min(10, d.change_24h))
        return round(50 + c * 3, 1)
