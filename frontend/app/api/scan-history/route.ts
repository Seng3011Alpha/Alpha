import { NextResponse } from "next/server";
import { getSessionUser } from "@/lib/quota";
import { createSupabaseServiceClient } from "@/lib/supabase/server";

function startOfTodayIso(): string {
  const now = new Date();
  const start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  return start.toISOString();
}

export async function GET() {
  const user = await getSessionUser();
  if (!user) return NextResponse.json({ error: "unauthorised" }, { status: 401 });

  const admin = createSupabaseServiceClient();
  const { data, error } = await admin
    .from("scan_results")
    .select("id, ticker, scanned_at, quote, indicators, report, news")
    .eq("user_id", user.id)
    .gte("scanned_at", startOfTodayIso())
    .order("scanned_at", { ascending: false });

  if (error) return NextResponse.json({ error: "db_error" }, { status: 500 });
  return NextResponse.json({ results: data ?? [] });
}
