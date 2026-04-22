import Link from "next/link";
import { ArrowRight, LineChart, Newspaper, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { TIERS } from "@/lib/tiers";
import { TierCard } from "@/components/tier-card";

export default function MarketingHome() {
  return (
    <div>
      <section className="container py-20">
        <div className="mx-auto max-w-2xl text-center">
          <p className="mb-3 text-xs uppercase tracking-widest text-muted-foreground">ASX event intelligence</p>
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
            Read the market. Not just the ticker.
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-balance text-muted-foreground">
            Scan any ASX listing and get price action, LLM-classified news sentiment, and a
            written daily report in one clean view.
          </p>
          <div className="mt-8 flex justify-center gap-3">
            <Button asChild size="lg" variant="accent">
              <Link href="/signup">
                Start free <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="/pricing">See pricing</Link>
            </Button>
          </div>
        </div>
      </section>

      <section className="container pb-16">
        <div className="grid gap-4 md:grid-cols-3">
          <FeatureCard
            icon={<LineChart className="h-5 w-5 text-accent" />}
            title="Live quotes and OHLC"
            body="Yahoo Finance pipeline with 1 month through 1 year charts and standard indicators."
          />
          <FeatureCard
            icon={<Sparkles className="h-5 w-5 text-accent" />}
            title="LLM sentiment"
            body="Claude reads each headline and classifies it, replacing the old keyword scorer."
          />
          <FeatureCard
            icon={<Newspaper className="h-5 w-5 text-accent" />}
            title="Written daily report"
            body="A short, cited analyst-style summary you can read in under a minute."
          />
        </div>
      </section>

      <section className="container pb-24">
        <div className="mb-6 flex items-end justify-between">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">Simple pricing</h2>
            <p className="text-sm text-muted-foreground">Upgrade is a demo only, no payment is taken.</p>
          </div>
          <Button asChild variant="ghost" size="sm">
            <Link href="/pricing">
              Full pricing <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {Object.values(TIERS).map((t) => (
            <TierCard key={t.id} tier={t} />
          ))}
        </div>
      </section>
    </div>
  );
}

function FeatureCard({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          {icon}
          <CardTitle className="text-base">{title}</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <CardDescription>{body}</CardDescription>
      </CardContent>
    </Card>
  );
}
