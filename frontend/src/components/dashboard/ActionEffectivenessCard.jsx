/**
 * ActionEffectivenessCard — shows which collection actions work best for this borrower.
 * Derived from historical interaction outcomes — this IS the feedback loop learning.
 */

import { BarChart2, CheckCircle2, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const ACTION_COLOR = {
  "Call":          "bg-blue-500",
  "Email":         "bg-teal-500",
  "Legal Notice":  "bg-orange-500",
  "Field Visit":   "bg-purple-500",
  "Payment Plan":  "bg-indigo-500",
  "NACH Trigger":  "bg-green-500",
  "WhatsApp":      "bg-teal-400",
};

function EffectivenessBar({ item }) {
  const pct = Math.round(item.success_rate * 100);
  const barColor = ACTION_COLOR[item.action_type] || "bg-primary";

  return (
    <div className={`rounded-lg p-3 ${item.recommended ? "bg-primary/8 border border-primary/20" : "bg-muted/30 border border-border"}`}>
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground">{item.action_type}</span>
          {item.recommended && (
            <span className="flex items-center gap-1 text-xs text-primary font-semibold">
              <Zap className="h-2.5 w-2.5" /> Best
            </span>
          )}
        </div>
        <div className="text-right">
          <span className={`text-sm font-bold ${pct >= 60 ? "text-green-600 dark:text-green-400" : pct >= 30 ? "text-amber-600 dark:text-amber-400" : "text-red-500"}`}>
            {pct}%
          </span>
          <span className="text-xs text-muted-foreground ml-1">({item.success_count}/{item.total_attempts})</span>
        </div>
      </div>
      <div className="h-1.5 rounded-full bg-muted overflow-hidden">
        <div className={`h-full rounded-full ${barColor} transition-all duration-700`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function ActionEffectivenessCard({ effectiveness = [], bestAction = "" }) {
  if (!effectiveness || effectiveness.length === 0) return null;

  return (
    <Card className="border-border">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <BarChart2 className="h-4 w-4 text-primary" />
          What Works for This Borrower
          <span className="text-xs font-normal text-muted-foreground">— learned from history</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-1 space-y-2">
        {effectiveness.map((e) => (
          <EffectivenessBar key={e.action_type} item={e} />
        ))}

        {bestAction && (
          <div className="mt-2 pt-2 border-t border-border">
            <div className="flex items-center gap-2 text-xs">
              <CheckCircle2 className="h-3.5 w-3.5 text-primary" />
              <span className="text-muted-foreground">History recommends:</span>
              <span className="font-semibold text-foreground">{bestAction}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
