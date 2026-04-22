export type Tier = "free" | "pro" | "enterprise";

export interface TierConfig {
  id: Tier;
  name: string;
  dailyScans: number;
  price: string;
  blurb: string;
  features: string[];
}

export const TIERS: Record<Tier, TierConfig> = {
  free: {
    id: "free",
    name: "Free",
    dailyScans: 1,
    price: "A$0",
    blurb: "Kick the tyres with a single daily scan.",
    features: [
      "1 stock scan per day",
      "Live ASX quotes",
      "LLM sentiment on headlines",
      "Written daily report",
    ],
  },
  pro: {
    id: "pro",
    name: "Pro",
    dailyScans: 3,
    price: "A$19",
    blurb: "For active retail investors who want a proper view.",
    features: [
      "3 stock scans per day",
      "Everything in Free",
      "1 month, 3 month, 6 month and 1 year charts",
      "Saved watchlist",
    ],
  },
  enterprise: {
    id: "enterprise",
    name: "Enterprise",
    dailyScans: Number.POSITIVE_INFINITY,
    price: "A$249",
    blurb: "Desk-grade access with no caps.",
    features: [
      "Unlimited scans",
      "Everything in Pro",
      "On-demand report refresh",
      "Priority data pipeline",
    ],
  },
};

export function limitFor(tier: Tier): number {
  return TIERS[tier].dailyScans;
}

export function isUnlimited(tier: Tier): boolean {
  return !Number.isFinite(TIERS[tier].dailyScans);
}
