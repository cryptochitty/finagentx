/**
 * FinAgentX – API client
 * Wraps all backend endpoints with typed functions.
 */
import axios from "axios";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({ baseURL: BASE, timeout: 30_000 });

// ─── Types ────────────────────────────────────────────────────────────────────

export interface MarketData {
  symbol:     string;
  price:      number;
  change_24h: number;
  volume_24h: number;
  sentiment:  string;
  trend:      string;
  rsi:        number;
}

export interface PortfolioData {
  wallet:       string;
  total_value:  number;
  cash_balance: number;
  holdings:     Record<string, number>;
  risk_score:   number;
}

export interface Trade {
  id:         number;
  symbol:     string;
  direction:  string;
  amount:     number;
  price:      number;
  status:     string;
  risk_score: number;
  tx_hash:    string | null;
  created_at: string;
}

export interface Payment {
  id:             number;
  recipient:      string;
  amount:         number;
  token:          string;
  schedule:       string;
  status:         string;
  next_execution: string | null;
}

export interface CycleDecision {
  agent:         string;
  decision_type: string;
  explanation:   string;
  payload:       Record<string, unknown>;
}

export interface CycleResult {
  wallet:      string;
  market_data: MarketData[];
  signals:     Array<{
    symbol:        string;
    action:        string;
    confidence:    number;
    rationale:     string;
    position_size: number;
  }>;
  risk: {
    score:    number;
    level:    string;
    approved: boolean;
    flags:    string[];
  };
  simulation: {
    roi_pct:       number;
    max_drawdown:  number;
    win_rate:      number;
    sharpe_ratio:  number;
    total_trades:  number;
    equity_curve:  Array<{ date: string; value: number }>;
  } | null;
  executed:   Trade[];
  decisions:  CycleDecision[];
  autonomous: boolean;
}

export interface SimulationResult {
  strategy:      string;
  roi_pct:       number;
  max_drawdown:  number;
  win_rate:      number;
  sharpe_ratio:  number;
  total_trades:  number;
  equity_curve:  Array<{ date: string; value: number }>;
  explanation:   string;
}

export interface ZKBadge {
  wallet:     string;
  verified:   boolean;
  scheme:     string;
  proof_hash: string;
  claims:     string[];
}

// ─── API functions ────────────────────────────────────────────────────────────

export const getPortfolio     = (wallet: string)              => api.get<PortfolioData>(`/portfolio/${wallet}`).then(r => r.data);
export const deposit          = (wallet: string, amount: number) => api.post(`/portfolio/${wallet}/deposit?amount=${amount}`).then(r => r.data);
export const getMarket        = (symbols?: string)            => api.get<MarketData[]>("/market", { params: symbols ? { symbols } : {} }).then(r => r.data);
export const runCycle         = (wallet: string, autonomous: boolean) => api.post<CycleResult>(`/cycle/${wallet}?autonomous=${autonomous}`).then(r => r.data);
export const getTrades        = (wallet: string)              => api.get<Trade[]>(`/trades/${wallet}`).then(r => r.data);
export const getPayments      = (wallet: string)              => api.get<Payment[]>(`/payments/${wallet}`).then(r => r.data);
export const createPayment    = (body: Record<string, unknown>) => api.post<Payment>("/payments", body).then(r => r.data);
export const runSimulation    = (body: Record<string, unknown>) => api.post<SimulationResult>("/simulate", body).then(r => r.data);
export const getDecisions     = (wallet: string)              => api.get<CycleDecision[]>(`/decisions/${wallet}`).then(r => r.data);
export const getZKBadge       = (wallet: string)              => api.get<ZKBadge>(`/zk/verify/${wallet}`).then(r => r.data);

// SSE – returns an EventSource for the live decision feed
export const createFeedStream = (wallet: string) =>
  new EventSource(`${BASE}/feed/${wallet}`);
