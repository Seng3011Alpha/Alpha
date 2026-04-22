import { NextResponse } from "next/server";
import { createSupabaseServerClient, createSupabaseServiceClient } from "@/lib/supabase/server";
import { TIERS, type Tier } from "@/lib/tiers";

export async function POST(req: Request) {
  const supabase = createSupabaseServerClient();
  const { data } = await supabase.auth.getUser();
  if (!data.user) {
    return NextResponse.json({ error: "unauthorised" }, { status: 401 });
  }
  const body = (await req.json().catch(() => ({}))) as { tier?: string };
  const requested = body.tier as Tier | undefined;
  if (!requested || !(requested in TIERS)) {
    return NextResponse.json({ error: "invalid_tier" }, { status: 400 });
  }
  const admin = createSupabaseServiceClient();
  const { error } = await admin
    .from("profiles")
    .update({ tier: requested })
    .eq("id", data.user.id);
  if (error) {
    return NextResponse.json({ error: "update_failed", detail: error.message }, { status: 500 });
  }
  return NextResponse.json({ ok: true, tier: requested });
}
