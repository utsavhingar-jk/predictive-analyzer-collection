/**
 * StrategyCard
 *
 * Displays the collection strategy recommendation:
 * - Priority score + rank
 * - Urgency badge
 * - Recommended action + channel
 * - SLA (next action in hours)
 * - Reasoning
 */

import { Target, Clock, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

const URGENCY_COLORS = {
  Critical: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300 border border-red-300 dark:border-red-700",
  High:     "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300 border border-orange-300 dark:border-orange-700",
  Medium:   "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300 border border-yellow-300 dark:border-yellow-700",
  Low:      "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300 border border-green-300 dark:border-green-700",
};

const CHANNEL_ICON = {
  "Call":               "📞",
  "Email":              "📧",
  "Legal":              "⚖️",
  "NACH":               "🏦",
  "Field Visit":        "🚗",
  "Anchor Escalation":  "🔗",
};

export function StrategyCard({ strategy }) {
  if (!strategy) return null;

  const urgencyClass = URGENCY_COLORS[strategy.urgency] || URGENCY_COLORS.Medium;
  const channelEmoji = CHANNEL_ICON[strategy.channel] || "📋";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Target className="h-4 w-4 text-primary" />
          Collection Strategy
        </CardTitle>
        <CardDescription>Optimized collection action plan</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Priority + urgency row */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">Priority Score</p>
            <p className="text-3xl font-black text-foreground">{strategy.priority_score}<span className="text-sm font-normal text-muted-foreground">/100</span></p>
            {strategy.priority_rank && (
              <p className="text-xs text-muted-foreground mt-0.5">Rank #{strategy.priority_rank} in portfolio</p>
            )}
          </div>
          <span className={`px-3 py-1.5 rounded-full text-sm font-bold ${urgencyClass}`}>
            {strategy.urgency}
          </span>
        </div>

        {/* Recommended action */}
        <div className="p-3 rounded-lg bg-primary/10 border border-primary/20">
          <p className="text-xs text-muted-foreground mb-1">Recommended Action</p>
          <p className="font-semibold text-primary text-sm">{strategy.recommended_action}</p>
        </div>

        {/* Channel + SLA */}
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 rounded-lg bg-muted/50">
            <p className="text-xs text-muted-foreground mb-1">Channel</p>
            <p className="text-sm font-medium text-foreground">
              {channelEmoji} {strategy.channel}
            </p>
          </div>
          <div className="p-3 rounded-lg bg-muted/50">
            <p className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
              <Clock className="h-3 w-3" /> SLA
            </p>
            <p className="text-sm font-medium text-foreground">
              {strategy.next_action_in_hours}h
            </p>
          </div>
        </div>

        {/* Automation flag */}
        {strategy.automation_flag && (
          <div className="flex items-center gap-2 text-xs text-blue-600 dark:text-blue-400">
            <Zap className="h-3.5 w-3.5" />
            <span>Eligible for automation</span>
          </div>
        )}

        {/* Reasoning */}
        {strategy.reason && (
          <p className="text-xs text-muted-foreground leading-relaxed border-t border-border pt-2">
            {strategy.reason}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
