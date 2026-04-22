import Link from "next/link";
import { LineChart } from "lucide-react";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-border">
        <div className="container flex h-14 items-center">
          <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <LineChart className="h-5 w-5 text-accent" />
            Alpha-2
          </Link>
        </div>
      </header>
      <main className="container flex flex-1 items-center justify-center py-12">
        <div className="w-full max-w-sm">{children}</div>
      </main>
    </div>
  );
}
