import { NextResponse } from "next/server";
import { getSessionUser } from "@/lib/quota";
import { createSupabaseServiceClient } from "@/lib/supabase/server";
import { normaliseTicker } from "@/lib/utils";

export async function DELETE(
  _req: Request,
  { params }: { params: { ticker: string } }
) {
  const user = await getSessionUser();
  if (!user) return NextResponse.json({ error: "unauthorised" }, { status: 401 });

  const ticker = normaliseTicker(decodeURIComponent(params.ticker));
  const admin = createSupabaseServiceClient();
  await admin
    .from("watchlist_items")
    .delete()
    .eq("user_id", user.id)
    .eq("ticker", ticker);

  return NextResponse.json({ ok: true });
}
