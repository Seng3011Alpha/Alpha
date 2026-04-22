import { TIERS } from "@/lib/tiers";
import { TierCard } from "@/components/tier-card";
import { createSupabaseServerClient, createSupabaseServiceClient } from "@/lib/supabase/server";

export default async function PricingPage() {
  const supabase = createSupabaseServerClient();
  const { data } = await supabase.auth.getUser();
  const user = data.user;

  let current: "free" | "pro" | "enterprise" | undefined;
  if (user) {
    const admin = createSupabaseServiceClient();
    const { data: profile } = await admin
      .from("profiles")
      .select("tier")
      .eq("id", user.id)
      .maybeSingle();
    current = (profile?.tier ?? "free") as typeof current;
  }

  return (
    <div className="container py-16">
      <div className="mx-auto max-w-xl text-center">
        <h1 className="text-3xl font-semibold tracking-tight">Pricing</h1>
        <p className="mt-3 text-muted-foreground">
          Three tiers. Upgrade is wired but the payment is a demo only for this assignment.
        </p>
      </div>
      <div className="mx-auto mt-10 grid max-w-5xl gap-4 md:grid-cols-3">
        {Object.values(TIERS).map((t) => (
          <TierCard key={t.id} tier={t} currentTier={current} signedIn={Boolean(user)} />
        ))}
      </div>
    </div>
  );
}
