import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        default: "border-border bg-muted text-muted-foreground",
        accent: "border-transparent bg-accent text-accent-foreground",
        success:
          "border-transparent bg-[hsl(var(--success)/0.12)] text-[hsl(var(--success))]",
        danger:
          "border-transparent bg-[hsl(var(--danger)/0.12)] text-[hsl(var(--danger))]",
        warning:
          "border-transparent bg-[hsl(var(--warning)/0.12)] text-[hsl(var(--warning))]",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}
