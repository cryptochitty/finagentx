"use client";
import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { getMarket, type MarketData } from "@/lib/api";

export default function MarketTicker() {
  const [data,    setData]    = useState<MarketData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = () =>
      getMarket("BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,HSKUSDT")
        .then(setData)
        .catch(console.error)
        .finally(() => setLoading(false));

    fetch();
    const interval = setInterval(fetch, 30_000);   // refresh every 30s
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="card flex gap-4 overflow-x-auto">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="shimmer h-10 w-32 flex-shrink-0" />
        ))}
      </div>
    );
  }

  return (
    <div className="card flex gap-4 overflow-x-auto py-2">
      {data.map(d => (
        <div key={d.symbol} className="flex items-center gap-2 flex-shrink-0 px-3 py-1.5
                                       bg-surface rounded-lg border border-surface-border">
          <span className="font-mono font-semibold text-sm text-slate-200">
            {d.symbol.replace("USDT", "")}
          </span>
          <span className="font-mono text-sm">
            ${d.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </span>
          <span className={`flex items-center gap-0.5 text-xs font-medium
            ${d.change_24h > 0 ? "text-green-400" : d.change_24h < 0 ? "text-red-400" : "text-slate-400"}`}>
            {d.change_24h > 0
              ? <TrendingUp  className="w-3 h-3" />
              : d.change_24h < 0
                ? <TrendingDown className="w-3 h-3" />
                : <Minus className="w-3 h-3" />
            }
            {Math.abs(d.change_24h).toFixed(2)}%
          </span>
          <span className={`text-xs px-1.5 py-0.5 rounded-full
            ${d.sentiment === "bullish" ? "text-green-400 bg-green-400/10"
            : d.sentiment === "bearish" ? "text-red-400 bg-red-400/10"
            : "text-slate-400 bg-slate-400/10"}`}>
            {d.sentiment}
          </span>
        </div>
      ))}
    </div>
  );
}
