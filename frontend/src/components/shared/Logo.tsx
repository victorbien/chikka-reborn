import { cn } from "@/lib/utils";

export interface LogoProps {
  /** Rendered height. The image keeps its 1920x660 proportions. */
  size?: "sm" | "md" | "lg";
  /** Set when adjacent text already names the app, so screen readers do not read it twice. */
  decorative?: boolean;
  className?: string;
}

const SIZE_CLASSES: Record<NonNullable<LogoProps["size"]>, string> = {
  sm: "h-7",
  md: "h-10",
  lg: "h-24 sm:h-32",
};

/** The Chikka Reborn logo. The one place the logo image is referenced. */
export function Logo({ size = "md", decorative = false, className }: LogoProps) {
  return (
    <img
      src="/logo.png"
      alt={decorative ? "" : "Chikka Reborn"}
      width={1920}
      height={660}
      className={cn("w-auto max-w-full select-none", SIZE_CLASSES[size], className)}
    />
  );
}
