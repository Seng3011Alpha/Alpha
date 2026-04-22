"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { RefreshCw } from "lucide-react";
import {
  analysisResponseSchema,
  newsResponseSchema,
  reportResponseSchema,
  stockResponseSchema,
  type AnalysisResponse,
  type ReportResponse,
} from "@/lib/api/schemas";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PriceChart } from "@/components/price-chart";
import { NewsCard } from "@/components/news-card";
import { MarkdownReport } from "@/components/markdown-report";
import { SentimentBadge } from "@/components/sentiment-badge";
import { formatPercent, formatPrice } from "@/lib/utils";
import { z } from "zod";

type ScanPayload = {
  ticker: string;
  stock: z.infer<typeof stockResponseSchema>;
  news: z.infer<typeof newsResponseSchema>;
  analysis: AnalysisResponse | null;
  report: ReportResponse | null;
  quota: { tier: "free" | "pro" | "enterprise"; used: number; limit: number; remaining: number; unlimited: boolean };
};

const PERIODS = ["1mo", "3mo", "6mo", "1y"] as const;

export function ScanView({ ticker }: { ticker: string }) {
  const router = useRouter();
  const [data, setData] = React.useState<ScanPayload | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [period, setPeriod] = React.useState<(typeof PERIODS)[number]>("1mo");
  const [chartLoading, setChartLoading] = React.useState(false);
  const [chartData, setChartData] = React.useState<AnalysisResponse | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    async function run() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch("/api/scan", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ ticker }),
        });
        const json = await res.json();
        if (!res.ok) {
          if (res.status === 429) {
            toast.error("Daily scan limit reached.");
            router.refresh();
            return;
          }
          throw new Error(json.detail ?? json.error ?? "scan_failed");
        }
        if (cancelled) return;
        const parsed: ScanPayload = {
          ticker: json.ticker,
          stock: stockResponseSchema.parse(json.stock),
          news: newsResponseSchema.parse(json.news),
          analysis: json.analysis ? analysisResponseSchema.parse(json.analysis) : null,
          report: json.report ? reportResponseSchema.parse(json.report) : null,
          quota: json.quota,
        };
        setData(parsed);
        setChartData(parsed.analysis);
        router.refresh();
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "scan_failed");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    run();
    return () => {
      cancelled = true;
    };
  }, [ticker, router]);

  async function onPeriodChange(next: string) {
    const p = next as (typeof PERIODS)[number];
    setPeriod(p);
    if (p === "1mo" && data?.analysis) {
      setChartData(data.analysis);
      return;
    }
    setChartLoading(true);
    try {
      const res = await fetch(`/api/analysis?stock=${encodeURIComponent(ticker)}&period=${p}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail ?? "analysis_failed");
      setChartData(analysisResponseSchema.parse(json));
    } catch {
      toast.error("Could not load that period.");
    } finally {
      setChartLoading(false);
    }
  }

  if (loading) return <ScanSkeleton />;
  if (error) return <ErrorState message={error} />;
  if (!data) return null;

  const quote = extractQuote(data.stock, ticker);
  const newsItems = data.news.events.map((e) => e.attribute as Parameters<typeof NewsCard>[0]["item"]);
  const changePct = typeof quote?.change_percent === "number" ? quote.change_percent : null;
  const changeColour =
    changePct === null ? "default" : changePct >= 0 ? "success" : "danger";

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">{ticker}.AX</h1>
            {quote?.company ? (
              <span className="text-sm text-muted-foreground">{quote.company}</span>
            ) : null}
          </div>
          <div className="mt-1 flex items-baseline gap-3">
            <span className="text-3xl font-semibold tabular-nums">
              {formatPrice(quote?.["Quote Price"] ?? null)}
            </span>
            <Badge variant={changeColour}>{formatPercent(changePct)}</Badge>
          </div>
        </div>
        <div className="text-xs text-muted-foreground">
          data source: {quote?.data_source ?? "unknown"} ·
          scans today: {data.quota.used} / {data.quota.unlimited ? "∞" : data.quota.limit}
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between gap-4 space-y-0">
            <CardTitle className="text-base">Price</CardTitle>
            <Tabs value={period} onValueChange={onPeriodChange}>
              <TabsList>
                {PERIODS.map((p) => (
                  <TabsTrigger key={p} value={p}>
                    {p}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </CardHeader>
          <CardContent>
            {chartLoading || !chartData ? (
              <Skeleton className="h-72 w-full" />
            ) : (
              <PriceChart
                data={chartData.ohlc_series.map((r) => ({ date: r.date, Close: r.Close }))}
              />
            )}
            <IndicatorsGrid indicators={chartData?.indicators ?? null} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Daily report</CardTitle>
              {data.report ? (
                <SentimentBadge sentiment={data.report.overall_sentiment} />
              ) : null}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {data.report ? (
              <>
                <MarkdownReport body={data.report.summary} />
                {data.report.key_drivers.length > 0 ? (
                  <BulletBlock title="Key drivers" items={data.report.key_drivers} tone="success" />
                ) : null}
                {data.report.risks.length > 0 ? (
                  <BulletBlock title="Risks" items={data.report.risks} tone="danger" />
                ) : null}
                <p className="text-xs text-muted-foreground">
                  model: {data.report.model} · articles considered: {data.report.articles_considered}
                  {data.report.cached ? " · cached" : ""}
                </p>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                Report could not be generated for this ticker.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
            Related news ({newsItems.length})
          </h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.refresh()}
            className="text-muted-foreground"
          >
            <RefreshCw className="h-3.5 w-3.5" /> refresh
          </Button>
        </div>
        {newsItems.length === 0 ? (
          <p className="text-sm text-muted-foreground">No recent news found for this ticker.</p>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {newsItems.map((n, i) => (
              <NewsCard key={`${n.link ?? n.title}-${i}`} item={n} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function IndicatorsGrid({
  indicators,
}: {
  indicators: AnalysisResponse["indicators"] | null;
}) {
  if (!indicators) return null;
  const rows: Array<[string, number | null | undefined]> = [
    ["MA5", indicators.MA5],
    ["MA20", indicators.MA20],
    ["Volatility (ann %)", indicators.volatility_annual_pct],
    ["52w high", indicators.week52_high],
    ["52w low", indicators.week52_low],
    ["Day high", indicators.days_high],
    ["Day low", indicators.days_low],
  ];
  return (
    <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-4">
      {rows.map(([k, v]) => (
        <div key={k} className="rounded-md border border-border/60 bg-muted/40 px-3 py-2">
          <dt className="text-muted-foreground">{k}</dt>
          <dd className="font-medium tabular-nums">
            {typeof v === "number" ? v.toFixed(2) : "-"}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function BulletBlock({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone: "success" | "danger";
}) {
  const dot =
    tone === "success" ? "bg-[hsl(var(--success))]" : "bg-[hsl(var(--danger))]";
  return (
    <div className="space-y-1.5">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</h3>
      <ul className="space-y-1.5 text-sm">
        {items.map((it, i) => (
          <li key={i} className="flex items-start gap-2">
            <span className={`mt-1.5 h-1.5 w-1.5 flex-none rounded-full ${dot}`} />
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ScanSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-7 w-40" />
        <Skeleton className="h-10 w-56" />
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <Skeleton className="h-96 lg:col-span-2" />
        <Skeleton className="h-96" />
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <Skeleton className="h-28" />
        <Skeleton className="h-28" />
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <Card className="mx-auto max-w-lg text-center">
      <CardHeader>
        <CardTitle>Could not complete the scan</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">{message}</p>
      </CardContent>
    </Card>
  );
}

type Quote = {
  ticker: string;
  company?: string;
  "Quote Price"?: number;
  "Previous Close"?: number;
  Open?: number;
  Volume?: number;
  change_percent?: number;
  data_source?: string;
};

function extractQuote(
  stock: z.infer<typeof stockResponseSchema>,
  ticker: string
): Quote | null {
  const target = `${ticker.toUpperCase()}.AX`;
  const quoteEvent = stock.events.find((e) => {
    if (e.event_type !== "Stock quote") return false;
    const attr = e.attribute as { ticker?: unknown };
    return attr?.ticker === target;
  });
  return (quoteEvent?.attribute ?? null) as Quote | null;
}
