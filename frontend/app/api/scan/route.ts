import { NextResponse } from "next/server";
import {
  fetchStock,
  fetchNews,
  fetchAnalysis,
  fetchReport,
} from "@/lib/api/backend";
import { normaliseTicker } from "@/lib/utils";
import { getSessionUser, readQuotaForUser, recordScan } from "@/lib/quota";
import { createSupabaseServiceClient } from "@/lib/supabase/server";

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

    // extract quote attribute for storage
    const quoteEvent = stock.events.find(
      (e) => e.event_type === "Stock quote" && (e.attribute as { ticker?: string }).ticker === ticker
    );
    // fire-and-forget: save full results for history tab
    void (async () => {
      try {
        await createSupabaseServiceClient()
          .from("scan_results")
          .insert({
            user_id: user.id,
            ticker,
            quote: quoteEvent?.attribute ?? null,
            indicators: analysis?.indicators ?? null,
            report: report
              ? {
                  summary: report.summary,
                  key_drivers: report.key_drivers,
                  risks: report.risks,
                  overall_sentiment: report.overall_sentiment,
                  generated_at: report.generated_at,
                  model: report.model,
                  articles_considered: report.articles_considered,
                }
              : null,
            news: news.events.map((e) => e.attribute),
          });
      } catch {
        // silent
      }
    })();

    const nextQuota = await readQuotaForUser(user.id);
    return NextResponse.json({ ticker, stock, news, analysis, report, quota: nextQuota });
  } catch (e) {
    const message = e instanceof Error ? e.message : "upstream_error";
    return NextResponse.json({ error: "upstream_error", detail: message }, { status: 502 });
  }
}
