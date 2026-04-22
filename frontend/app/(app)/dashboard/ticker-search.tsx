"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function TickerSearch({ quotaRemaining }: { quotaRemaining: number }) {
  const router = useRouter();
  const [value, setValue] = React.useState("");
  const exhausted = quotaRemaining <= 0 && Number.isFinite(quotaRemaining);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const raw = value.trim().toUpperCase();
    if (!raw) return;
    const base = raw.replace(/\.AX$/, "");
    router.push(`/scan/${encodeURIComponent(base)}`);
  }

  return (
    <form onSubmit={onSubmit} className="flex gap-2">
      <div className="relative flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Search ASX ticker e.g. BHP"
          className="pl-9"
          aria-label="ASX ticker"
        />
      </div>
      {exhausted ? (
        <Button type="button" variant="accent" onClick={() => router.push("/pricing")}>
          Upgrade to scan
        </Button>
      ) : (
        <Button type="submit" variant="accent">
          Scan
        </Button>
      )}
    </form>
  );
}
