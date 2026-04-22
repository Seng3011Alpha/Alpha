import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPrice(n: number | null | undefined, currency = "A$"): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  return `${currency}${n.toFixed(2)}`;
}

export function formatPercent(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

export function normaliseTicker(raw: string): string {
  const t = raw.trim().toUpperCase();
  if (!t) return "";
  return t.endsWith(".AX") ? t : `${t}.AX`;
}

export function stripAxSuffix(t: string): string {
  return t.replace(/\.AX$/i, "");
}
