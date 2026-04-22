import { NextResponse } from "next/server";
import { fetchAnalysis } from "@/lib/api/backend";
import { normaliseTicker } from "@/lib/utils";
import { getSessionUser } from "@/lib/quota";

export async function GET(req: Request) {
  const user = await getSessionUser();
  if (!user) return NextResponse.json({ error: "unauthorised" }, { status: 401 });

  const url = new URL(req.url);
  const stock = url.searchParams.get("stock");
  const period = url.searchParams.get("period") ?? "1mo";
  if (!stock) return NextResponse.json({ error: "missing_stock" }, { status: 400 });

  try {
    const data = await fetchAnalysis(normaliseTicker(stock), period);
    return NextResponse.json(data);
  } catch (e) {
    const message = e instanceof Error ? e.message : "upstream_error";
    return NextResponse.json({ error: "upstream_error", detail: message }, { status: 502 });
  }
}
