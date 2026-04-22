import {
  analysisResponseSchema,
  newsResponseSchema,
  reportResponseSchema,
  stockResponseSchema,
  type AnalysisResponse,
  type ReportResponse,
} from "./schemas";

function getBase(): string {
  const b = process.env.BACKEND_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!b) {
    throw new Error("BACKEND_API_BASE_URL is not configured");
  }
  return b.replace(/\/$/, "");
}

async function get<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${getBase()}${path}`, {
    ...init,
    headers: { accept: "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`backend ${res.status} on ${path}`);
  }
  return (await res.json()) as T;
}

export async function fetchStock(ticker: string, includeOhlc = true) {
  const t = encodeURIComponent(ticker);
  const raw = await get<unknown>(`/api/stock?ticker=${t}&include_ohlc=${includeOhlc}`);
  return stockResponseSchema.parse(raw);
}

export async function fetchNews(ticker: string, limit = 15) {
  const t = encodeURIComponent(ticker);
  const raw = await get<unknown>(`/api/news?ticker=${t}&limit=${limit}`);
  return newsResponseSchema.parse(raw);
}

export async function fetchAnalysis(stock: string, period = "1mo"): Promise<AnalysisResponse> {
  const s = encodeURIComponent(stock);
  const raw = await get<unknown>(`/api/analysis?stock=${s}&period=${period}`);
  return analysisResponseSchema.parse(raw);
}

export async function fetchReport(stock: string, forceRefresh = false): Promise<ReportResponse> {
  const s = encodeURIComponent(stock);
  const raw = await get<unknown>(`/api/report?stock=${s}&force_refresh=${forceRefresh}`);
  return reportResponseSchema.parse(raw);
}
