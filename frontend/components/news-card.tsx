import { ExternalLink } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { SentimentBadge } from "@/components/sentiment-badge";

type NewsItem = {
  title: string | null;
  source?: string | null;
  published?: string | null;
  link?: string | null;
  sentiment: "positive" | "negative" | "neutral";
  impact_score: number;
};

export function NewsCard({ item }: { item: NewsItem }) {
  const score = Math.max(0, Math.min(1, item.impact_score));
  const fillClass =
    item.sentiment === "positive"
      ? "bg-[hsl(var(--success))]"
      : item.sentiment === "negative"
      ? "bg-[hsl(var(--danger))]"
      : "bg-muted-foreground";
  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{item.source ?? "unknown source"}</span>
          <span>{item.published ? formatDate(item.published) : ""}</span>
        </div>
        <a
          href={item.link ?? "#"}
          target="_blank"
          rel="noreferrer"
          className="group flex items-start gap-2 text-sm font-medium leading-snug hover:text-accent"
        >
          <span className="flex-1">{item.title ?? "Untitled"}</span>
          <ExternalLink className="mt-0.5 h-3.5 w-3.5 text-muted-foreground group-hover:text-accent" />
        </a>
        <div className="flex items-center justify-between gap-3">
          <SentimentBadge sentiment={item.sentiment} score={score} />
          <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
            <div className={`h-full ${fillClass}`} style={{ width: `${score * 100}%` }} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function formatDate(raw: string): string {
  try {
    const d = new Date(raw);
    if (Number.isNaN(d.getTime())) return raw;
    return d.toLocaleDateString("en-AU", { day: "numeric", month: "short" });
  } catch {
    return raw;
  }
}
