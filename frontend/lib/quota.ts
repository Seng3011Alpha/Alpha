import { createSupabaseServerClient, createSupabaseServiceClient } from "@/lib/supabase/server";
import { limitFor, isUnlimited, type Tier } from "@/lib/tiers";

export interface QuotaState {
  tier: Tier;
  used: number;
  limit: number;
  remaining: number;
  unlimited: boolean;
}

export async function getSessionUser() {
  const supabase = createSupabaseServerClient();
  const { data } = await supabase.auth.getUser();
  return data.user;
}

export async function readQuotaForUser(userId: string): Promise<QuotaState> {
  const admin = createSupabaseServiceClient();
  const [{ data: profile }, { count }] = await Promise.all([
    admin.from("profiles").select("tier").eq("id", userId).maybeSingle(),
    admin
      .from("scan_usage")
      .select("id", { head: true, count: "exact" })
      .eq("user_id", userId)
      .gte("scanned_at", startOfTodayIso()),
  ]);

  const tier = (profile?.tier ?? "free") as Tier;
  const used = count ?? 0;
  const unlimited = isUnlimited(tier);
  const limit = unlimited ? Number.POSITIVE_INFINITY : limitFor(tier);
  const remaining = unlimited ? Number.POSITIVE_INFINITY : Math.max(limit - used, 0);
  return { tier, used, limit, remaining, unlimited };
}

export async function recordScan(userId: string, ticker: string) {
  const admin = createSupabaseServiceClient();
  await admin.from("scan_usage").insert({ user_id: userId, ticker });
}

function startOfTodayIso(): string {
  const now = new Date();
  const start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  return start.toISOString();
}
