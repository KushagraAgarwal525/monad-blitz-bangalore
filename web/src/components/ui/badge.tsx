import { cn } from "@/lib/utils";

export function Badge({ className, variant = "default", ...props }: React.HTMLAttributes<HTMLDivElement> & { variant?: "default" | "success" | "destructive" }) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        variant === "success" && "border-green-200 bg-green-50 text-green-700",
        variant === "destructive" && "border-red-200 bg-red-50 text-red-700",
        variant === "default" && "border-zinc-200 bg-zinc-50",
        className
      )}
      {...props}
    />
  );
}
