import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { Tier } from "@/lib/tiers";

export function QuotaWall({ tier, used, limit }: { tier: Tier; used: number; limit: number }) {
  return (
    <Card className="mx-auto max-w-xl text-center">
      <CardHeader>
        <CardTitle>Daily scan limit reached</CardTitle>
        <CardDescription>
          Your {tier} plan allows {limit} scan{limit === 1 ? "" : "s"} per day. You have used {used}.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex justify-center gap-3">
        <Button asChild variant="accent">
          <Link href="/pricing">Upgrade plan</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/dashboard">Back to dashboard</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
