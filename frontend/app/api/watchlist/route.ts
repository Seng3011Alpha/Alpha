import { NextResponse } from "next/server";
import { getSessionUser } from "@/lib/quota";
import { createSupabaseServiceClient } from "@/lib/supabase/server";
import { normaliseTicker } from "@/lib/utils";

export async function GET() {
  const user = await getSessionUser();
  if (!user) return NextResponse.json({ error: "unauthorised" }, { status: 401 });

  const admin = createSupabaseServiceClient();
  const { data, error } = await admin
    .from("watchlist_items")
    .select("ticker, added_at")
    .eq("user_id", user.id)
    .order("added_at", { ascending: false });

  if (error) return NextResponse.json({ error: "db_error" }, { status: 500 });
  return NextResponse.json({ items: data ?? [] });
}

export async function POST(req: Request) {
  const user = await getSessionUser();
  if (!user) return NextResponse.json({ error: "unauthorised" }, { status: 401 });

  const body = (await req.json().catch(() => ({}))) as { ticker?: string };
  const ticker = normaliseTicker(String(body.ticker ?? "").trim());
  if (!ticker) return NextResponse.json({ error: "missing_ticker" }, { status: 400 });

  const admin = createSupabaseServiceClient();
  const { error } = await admin
    .from("watchlist_items")
    .upsert({ user_id: user.id, ticker }, { onConflict: "user_id,ticker" });

  if (error) return NextResponse.json({ error: "db_error" }, { status: 500 });
  return NextResponse.json({ ok: true });
}
