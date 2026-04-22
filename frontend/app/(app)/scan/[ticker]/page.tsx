import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { readQuotaForUser } from "@/lib/quota";
import { ScanView } from "./scan-view";
import { QuotaWall } from "./quota-wall";

export default async function ScanPage({ params }: { params: { ticker: string } }) {
  const supabase = createSupabaseServerClient();
  const { data } = await supabase.auth.getUser();
  if (!data.user) redirect(`/login?next=/scan/${params.ticker}`);
  const quota = await readQuotaForUser(data.user.id);

  const ticker = decodeURIComponent(params.ticker).toUpperCase().replace(/\.AX$/, "");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Button asChild variant="ghost" size="sm">
          <Link href="/dashboard">
            <ArrowLeft className="h-4 w-4" /> Dashboard
          </Link>
        </Button>
      </div>

      {quota.remaining > 0 || quota.unlimited ? (
        <ScanView ticker={ticker} />
      ) : (
        <QuotaWall tier={quota.tier} used={quota.used} limit={quota.limit} />
      )}
    </div>
  );
}
