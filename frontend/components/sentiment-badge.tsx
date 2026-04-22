import { Badge } from "@/components/ui/badge";

type Sentiment = "positive" | "negative" | "neutral";

export function SentimentBadge({ sentiment, score }: { sentiment: Sentiment; score?: number }) {
  const variant = sentiment === "positive" ? "success" : sentiment === "negative" ? "danger" : "default";
  const label = sentiment.charAt(0).toUpperCase() + sentiment.slice(1);
  return (
    <Badge variant={variant}>
      {label}
      {typeof score === "number" ? ` · ${score.toFixed(2)}` : ""}
    </Badge>
  );
}
