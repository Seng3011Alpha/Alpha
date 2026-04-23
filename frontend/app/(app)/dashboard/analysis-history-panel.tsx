"use client";

import * as React from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SentimentBadge } from "@/components/sentiment-badge";
import { MarkdownReport } from "@/components/markdown-report";
import { formatPercent, formatPrice } from "@/lib/utils";

type Quote = {
  "Quote Price"?: number | null;
  change_percent?: number | null;
  company?: string | null;
};

type Report = {
  summary?: string;
  key_drivers?: string[];
  risks?: string[];
  overall_sentiment?: "positive" | "negative" | "neutral";
  generated_at?: string;
  model?: string;
};

type ScanResult = {
  id: string;
  ticker: string;
  scanned_at: string;
  quote: Quote | null;
  indicators: Record<string, number | null> | null;
  report: Report | null;
  news: Record<string, unknown>[] | null;
};

export function AnalysisHistoryPanel({ initialResults }: { initialResults: ScanResult[] }) {
  const [expanded, setExpanded] = React.useState<Set<string>>(new Set());

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  if (initialResults.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No scans today. Run an analysis from your watchlist or search above.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {initialResults.map((r) => {
        const isOpen = expanded.has(r.id);
        const changePct = r.quote?.change_percent ?? null;
        const changeVariant =
          changePct === null ? "default" : changePct >= 0 ? "success" : "danger";

        return (
          <Card key={r.id}>
            <CardHeader className="pb-2">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex flex-wrap items-center gap-2">
                  <CardTitle className="text-base">{r.ticker}</CardTitle>
                  {r.quote?.company ? (
                    <span className="text-sm text-muted-foreground">{r.quote.company}</span>
                  ) : null}
                  <span className="text-lg font-semibold tabular-nums">
                    {formatPrice(r.quote?.["Quote Price"] ?? null)}
                  </span>
                  <Badge variant={changeVariant}>{formatPercent(changePct)}</Badge>
                  {r.report?.overall_sentiment ? (
                    <SentimentBadge sentiment={r.report.overall_sentiment} />
                  ) : null}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">
                    {new Date(r.scanned_at).toLocaleTimeString("en-AU", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    onClick={() => toggle(r.id)}
                    aria-label={isOpen ? "Collapse" : "Expand"}
                  >
                    {isOpen ? (
                      <ChevronUp className="h-4 w-4" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>
            </CardHeader>

            {isOpen ? (
              <CardContent className="space-y-4 pt-0">
                {r.report?.summary ? (
                  <MarkdownReport body={r.report.summary} />
                ) : null}

                {r.report?.key_drivers && r.report.key_drivers.length > 0 ? (
                  <div>
                    <p className="mb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Key drivers
                    </p>
                    <ul className="space-y-1">
                      {r.report.key_drivers.map((d, i) => (
                        <li key={i} className="flex gap-2 text-sm text-success">
                          <span>+</span>
                          <span>{d}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {r.report?.risks && r.report.risks.length > 0 ? (
                  <div>
                    <p className="mb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Risks
                    </p>
                    <ul className="space-y-1">
                      {r.report.risks.map((risk, i) => (
                        <li key={i} className="flex gap-2 text-sm text-destructive">
                          <span>-</span>
                          <span>{risk}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {r.indicators ? (
                  <div>
                    <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Indicators
                    </p>
                    <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                      {[
                        ["MA5", r.indicators.MA5],
                        ["MA20", r.indicators.MA20],
                        ["52w high", r.indicators.week52_high],
                        ["52w low", r.indicators.week52_low],
                      ].map(([label, val]) => (
                        <div key={String(label)} className="rounded border border-border p-2">
                          <p className="text-xs text-muted-foreground">{label}</p>
                          <p className="font-medium tabular-nums">
                            {val != null ? `A$${Number(val).toFixed(2)}` : "-"}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {r.report?.model ? (
                  <p className="text-xs text-muted-foreground">
                    model: {r.report.model}
                  </p>
                ) : null}
              </CardContent>
            ) : null}
          </Card>
        );
      })}
    </div>
  );
}
