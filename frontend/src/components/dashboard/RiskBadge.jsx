import { cn, getRiskColor } from "@/lib/utils";

export function RiskBadge({ risk, className }) {
  const colors = getRiskColor(risk);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        colors.bg,
        colors.text,
        className
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", colors.dot)} />
      {risk}
    </span>
  );
}
