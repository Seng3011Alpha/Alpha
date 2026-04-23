import { redirect } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { readQuotaForUser } from "@/lib/quota";
import { createSupabaseServerClient, createSupabaseServiceClient } from "@/lib/supabase/server";
import { TickerSearch } from "./ticker-search";
import { WatchlistPanel } from "./watchlist-panel";
import { AnalysisHistoryPanel } from "./analysis-history-panel";

function startOfTodayIso(): string {
  const now = new Date();
  const start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  return start.toISOString();
}

export default async function DashboardPage() {
  const supabase = createSupabaseServerClient();
  const { data } = await supabase.auth.getUser();
  if (!data.user) redirect("/login");

  const admin = createSupabaseServiceClient();
  const userId = data.user.id;

  const [quota, { data: watchlistRows }, { data: historyRows }] = await Promise.all([
    readQuotaForUser(userId),
    admin
      .from("watchlist_items")
      .select("ticker, added_at")
      .eq("user_id", userId)
      .order("added_at", { ascending: false }),
    admin
      .from("scan_results")
      .select("id, ticker, scanned_at, quote, indicators, report, news")
      .eq("user_id", userId)
      .gte("scanned_at", startOfTodayIso())
      .order("scanned_at", { ascending: false }),
  ]);

  const watchlistItems = watchlistRows ?? [];
  const historyItems = historyRows ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Scan any ASX ticker. Your plan allows{" "}
            {quota.unlimited ? "unlimited" : `${quota.limit} scan${quota.limit === 1 ? "" : "s"}`}{" "}
            per day.
          </p>
        </div>
        <Badge variant={quota.remaining > 0 ? "success" : "danger"}>
          {quota.remaining > 0
            ? `${quota.unlimited ? "∞" : quota.remaining} remaining today`
            : "quota reached"}
        </Badge>
      </div>

      <TickerSearch quotaRemaining={quota.remaining} />

      <Tabs defaultValue="watchlist">
        <TabsList>
          <TabsTrigger value="watchlist">
            Watchlist {watchlistItems.length > 0 ? `(${watchlistItems.length})` : ""}
          </TabsTrigger>
          <TabsTrigger value="history">
            Today&apos;s analysis {historyItems.length > 0 ? `(${historyItems.length})` : ""}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="watchlist">
          <WatchlistPanel initialItems={watchlistItems} />
        </TabsContent>

        <TabsContent value="history">
          <AnalysisHistoryPanel initialResults={historyItems} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
