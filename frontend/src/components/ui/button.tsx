import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-control text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 bevel",
  {
    variants: {
      variant: {
        primary: "bg-accent text-accent-fg hover:brightness-110",
        secondary: "border border-border bg-surface-raised text-fg hover:brightness-125",
        ghost: "text-fg hover:bg-surface-raised",
        destructive: "bg-danger text-danger-fg hover:brightness-110",
      },
      size: {
        md: "min-h-11 px-4",
        sm: "min-h-11 px-3 md:min-h-9",
        icon: "size-11 md:size-10",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export function Button({ className, variant, size, asChild = false, type, ...props }: ButtonProps) {
  const Component = asChild ? Slot : "button";
  return (
    <Component
      className={cn(buttonVariants({ variant, size }), className)}
      type={asChild ? undefined : (type ?? "button")}
      {...props}
    />
  );
}
