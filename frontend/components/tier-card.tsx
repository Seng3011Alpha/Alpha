"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import type { TierConfig } from "@/lib/tiers";

export function TierCard({
  tier,
  currentTier,
  signedIn,
}: {
  tier: TierConfig;
  currentTier?: TierConfig["id"];
  signedIn?: boolean;
}) {
  const router = useRouter();
  const [loading, setLoading] = React.useState(false);
  const isCurrent = currentTier === tier.id;

  async function choose() {
    if (!signedIn) {
      router.push(`/signup`);
      return;
    }
    setLoading(true);
    //simulate a short payment flow
    await new Promise((r) => setTimeout(r, 1500));
    const res = await fetch("/api/subscribe", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ tier: tier.id }),
    });
    setLoading(false);
    if (!res.ok) {
      toast.error("Could not update subscription.");
      return;
    }
    toast.success("Subscription activated (demo mode, no payment taken)");
    router.refresh();
  }

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <CardTitle>{tier.name}</CardTitle>
        <CardDescription>{tier.blurb}</CardDescription>
      </CardHeader>
      <CardContent className="flex-1">
        <div className="mb-4 flex items-baseline gap-1">
          <span className="text-3xl font-semibold tracking-tight">{tier.price}</span>
          <span className="text-sm text-muted-foreground">/ month</span>
        </div>
        <ul className="space-y-2 text-sm">
          {tier.features.map((f) => (
            <li key={f} className="flex items-start gap-2">
              <Check className="mt-0.5 h-4 w-4 text-accent" />
              <span>{f}</span>
            </li>
          ))}
        </ul>
      </CardContent>
      <CardFooter>
        <Button
          className="w-full"
          variant={tier.id === "pro" ? "accent" : "default"}
          onClick={choose}
          disabled={loading || isCurrent}
        >
          {isCurrent ? "Current plan" : loading ? "Activating…" : signedIn ? "Choose plan" : "Get started"}
        </Button>
      </CardFooter>
    </Card>
  );
}
