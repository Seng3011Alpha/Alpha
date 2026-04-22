import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TickerSearch } from "./ticker-search";
import { readQuotaForUser } from "@/lib/quota";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

const WATCHLIST = [
  { ticker: "BHP", name: "BHP Group" },
  { ticker: "CBA", name: "Commonwealth Bank" },
  { ticker: "NAB", name: "National Australia Bank" },
  { ticker: "WBC", name: "Westpac" },
  { ticker: "ANZ", name: "ANZ Group" },
  { ticker: "RIO", name: "Rio Tinto" },
  { ticker: "WDS", name: "Woodside Energy" },
  { ticker: "CSL", name: "CSL Limited" },
];

export default async function DashboardPage() {
  const supabase = createSupabaseServerClient();
  const { data } = await supabase.auth.getUser();
  if (!data.user) redirect("/login");
  const quota = await readQuotaForUser(data.user.id);

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Scan any ASX ticker. Your plan allows{" "}
            {quota.unlimited ? "unlimited" : `${quota.limit} scan${quota.limit === 1 ? "" : "s"}`} per day.
          </p>
        </div>
        <Badge variant={quota.remaining > 0 ? "success" : "danger"}>
          {quota.remaining > 0
            ? `${quota.unlimited ? "∞" : quota.remaining} remaining today`
            : "quota reached"}
        </Badge>
      </div>

      <TickerSearch quotaRemaining={quota.remaining} />

      <section>
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-muted-foreground">
          Popular ASX listings
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {WATCHLIST.map((w) => (
            <Link key={w.ticker} href={`/scan/${w.ticker}`}>
              <Card className="transition-colors hover:border-accent/60">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">{w.ticker}.AX</CardTitle>
                  <CardDescription>{w.name}</CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-muted-foreground">
                    Click to scan and fetch a fresh report.
                  </p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
