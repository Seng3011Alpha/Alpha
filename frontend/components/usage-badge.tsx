import { Badge } from "@/components/ui/badge";
import { isUnlimited, TIERS, type Tier } from "@/lib/tiers";

export function UsageBadge({ tier, used }: { tier: Tier; used: number }) {
  const cfg = TIERS[tier];
  const unlimited = isUnlimited(tier);
  return (
    <div className="flex items-center gap-2">
      <Badge variant="default">{cfg.name}</Badge>
      <span className="text-xs text-muted-foreground">
        scans today: {used} / {unlimited ? "∞" : cfg.dailyScans}
      </span>
    </div>
  );
}
