import { NextResponse } from "next/server";
import {
  fetchStock,
  fetchNews,
  fetchAnalysis,
  fetchReport,
} from "@/lib/api/backend";
import { normaliseTicker } from "@/lib/utils";
import { getSessionUser, readQuotaForUser, recordScan } from "@/lib/quota";

export async function POST(req: Request) {
  const user = await getSessionUser();
  if (!user) return NextResponse.json({ error: "unauthorised" }, { status: 401 });

  const body = (await req.json().catch(() => ({}))) as { ticker?: string };
  const tickerRaw = String(body.ticker ?? "").trim();
  if (!tickerRaw) {
    return NextResponse.json({ error: "missing_ticker" }, { status: 400 });
  }
  const ticker = normaliseTicker(tickerRaw);

  const quota = await readQuotaForUser(user.id);
  if (!quota.unlimited && quota.remaining <= 0) {
    return NextResponse.json(
      { error: "quota_exceeded", limit: quota.limit, used: quota.used, tier: quota.tier },
      { status: 429 }
    );
  }

  try {
    const [stock, news, analysis, report] = await Promise.all([
      fetchStock(ticker, true),
      fetchNews(ticker, 15),
      fetchAnalysis(ticker, "1mo").catch(() => null),
      fetchReport(ticker, false).catch(() => null),
    ]);
    await recordScan(user.id, ticker);
    const nextQuota = await readQuotaForUser(user.id);
    return NextResponse.json({ ticker, stock, news, analysis, report, quota: nextQuota });
  } catch (e) {
    const message = e instanceof Error ? e.message : "upstream_error";
    return NextResponse.json({ error: "upstream_error", detail: message }, { status: 502 });
  }
}
