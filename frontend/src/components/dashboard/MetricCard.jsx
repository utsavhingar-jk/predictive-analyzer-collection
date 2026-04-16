import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

/**
 * KPI metric card for the executive dashboard.
 */
export function MetricCard({ title, value, subtitle, icon: Icon, trend, trendLabel, className }) {
  const TrendIcon =
    trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;

  const trendColor =
    trend === "up" ? "text-green-600 dark:text-green-400" :
    trend === "down" ? "text-red-600 dark:text-red-400" :
    "text-muted-foreground";

  return (
    <Card className={cn("relative overflow-hidden group transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-primary/5 border-border/60 hover:border-primary/40 bg-gradient-to-br from-card to-muted/10", className)}>
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="text-2xl font-bold text-foreground">{value}</p>
            {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
          </div>
          {Icon && (
            <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0 group-hover:bg-primary/20 transition-colors duration-300">
              <Icon className="h-5 w-5 text-primary group-hover:scale-110 transition-transform duration-300" />
            </div>
          )}
        </div>
        {trendLabel && (
          <div className={cn("flex items-center gap-1 mt-3 text-xs font-medium", trendColor)}>
            <TrendIcon className="h-3.5 w-3.5" />
            {trendLabel}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
