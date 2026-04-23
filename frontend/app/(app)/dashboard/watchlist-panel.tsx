"use client";

import * as React from "react";
import { toast } from "sonner";
import { Trash2, BarChart2, Plus, Search } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { stripAxSuffix } from "@/lib/utils";

type WatchlistItem = { ticker: string; added_at: string };

export function WatchlistPanel({ initialItems }: { initialItems: WatchlistItem[] }) {
  const [items, setItems] = React.useState(initialItems);
  const [query, setQuery] = React.useState("");
  const [adding, setAdding] = React.useState(false);

  async function addTicker(e: React.FormEvent) {
    e.preventDefault();
    const raw = query.trim().toUpperCase();
    if (!raw) return;
    setAdding(true);
    try {
      const res = await fetch("/api/watchlist", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ ticker: raw }),
      });
      if (!res.ok) {
        const json = await res.json();
        throw new Error(json.error ?? "failed");
      }
      const normalised = raw.endsWith(".AX") ? raw : `${raw}.AX`;
      if (!items.find((i) => i.ticker === normalised)) {
        setItems([{ ticker: normalised, added_at: new Date().toISOString() }, ...items]);
      }
      setQuery("");
      toast.success(`${normalised} added to watchlist`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not add ticker");
    } finally {
      setAdding(false);
    }
  }

  async function removeTicker(ticker: string) {
    const base = encodeURIComponent(stripAxSuffix(ticker));
    await fetch(`/api/watchlist/${base}`, { method: "DELETE" });
    setItems((prev) => prev.filter((i) => i.ticker !== ticker));
    toast.success(`${ticker} removed`);
  }

  return (
    <div className="space-y-4">
      <form onSubmit={addTicker} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Add ASX ticker e.g. WES"
            className="pl-9"
            aria-label="Add to watchlist"
          />
        </div>
        <Button type="submit" variant="outline" disabled={adding}>
          <Plus className="mr-1 h-4 w-4" />
          Add
        </Button>
      </form>

      {items.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No stocks in your watchlist yet. Search above to add one.
        </p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {items.map((item) => {
            const base = stripAxSuffix(item.ticker);
            return (
              <Card key={item.ticker} className="flex flex-col">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-base">{item.ticker}</CardTitle>
                      <CardDescription className="text-xs">
                        Added {new Date(item.added_at).toLocaleDateString("en-AU")}
                      </CardDescription>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                      onClick={() => removeTicker(item.ticker)}
                      aria-label={`Remove ${item.ticker}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="mt-auto pt-0">
                  <Button asChild variant="accent" size="sm" className="w-full">
                    <a href={`/scan/${base}`}>
                      <BarChart2 className="mr-1 h-3.5 w-3.5" />
                      Run analysis
                    </a>
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
