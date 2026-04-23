import { Navbar } from "@/components/navbar";

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="flex-1">{children}</main>
      <footer className="border-t border-border py-6 text-center text-xs text-muted-foreground">
        Tickertone · built for SENG3011 · data for research only, not investment advice
      </footer>
    </div>
  );
}
