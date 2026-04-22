import Link from "next/link";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { readQuotaForUser } from "@/lib/quota";
import { UsageBadge } from "@/components/usage-badge";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { LineChart } from "lucide-react";

export async function Navbar() {
  const supabase = createSupabaseServerClient();
  const { data } = await supabase.auth.getUser();
  const user = data.user;

  let usage: { tier: "free" | "pro" | "enterprise"; used: number } | null = null;
  if (user) {
    const q = await readQuotaForUser(user.id);
    usage = { tier: q.tier, used: q.used };
  }

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border bg-background/80 backdrop-blur">
      <div className="container flex h-14 items-center justify-between">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <LineChart className="h-5 w-5 text-accent" />
          Alpha-2
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          {user ? (
            <>
              <Link href="/dashboard" className="text-muted-foreground hover:text-foreground">
                Dashboard
              </Link>
              <Link href="/pricing" className="text-muted-foreground hover:text-foreground">
                Pricing
              </Link>
              <Link href="/account" className="text-muted-foreground hover:text-foreground">
                Account
              </Link>
              {usage ? <UsageBadge tier={usage.tier} used={usage.used} /> : null}
              <ThemeToggle />
            </>
          ) : (
            <>
              <Link href="/pricing" className="text-muted-foreground hover:text-foreground">
                Pricing
              </Link>
              <ThemeToggle />
              <Button asChild size="sm" variant="outline">
                <Link href="/login">Log in</Link>
              </Button>
              <Button asChild size="sm" variant="accent">
                <Link href="/signup">Sign up</Link>
              </Button>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
