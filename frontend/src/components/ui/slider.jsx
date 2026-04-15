import { cn } from "@/lib/utils";

/**
 * Simple native range slider styled to match the design system.
 */
export function Slider({ label, value, onChange, min = 0, max = 100, step = 1, suffix = "%", className }) {
  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex justify-between text-sm">
        <span className="font-medium text-foreground">{label}</span>
        <span className="font-semibold text-primary">
          {value}
          {suffix}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className={cn(
          "w-full h-2 rounded-full appearance-none cursor-pointer",
          "bg-secondary accent-primary"
        )}
      />
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>
          {min}
          {suffix}
        </span>
        <span>
          {max}
          {suffix}
        </span>
      </div>
    </div>
  );
}
