/**
 * PaymentBehaviorCard
 *
 * Displays a borrower's payment personality profile:
 * - Behavior type badge
 * - On-time ratio, avg delay, trend
 * - NACH recommendation flag
 * - Risk score gauge
 * - Behavior summary text
 */

import { UserCheck, TrendingUp, TrendingDown, Minus, AlertCircle, CheckCircle, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ExplainabilityPanel } from "@/components/dashboard/ExplainabilityPanel";

const BEHAVIOR_COLORS = {
  "Consistent Payer":       "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  "Occasional Late Payer":  "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
  "Reminder Driven Payer":  "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
  "Partial Payment Payer":  "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  "Chronic Delayed Payer":  "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  "High Risk Defaulter":    "bg-rose-100 text-rose-900 dark:bg-rose-900/50 dark:text-rose-300",
};

const RISK_GAUGE_COLOR = (score) => {
  if (score >= 75) return "bg-red-500";
  if (score >= 45) return "bg-amber-500";
  return "bg-green-500";
};

function TrendIcon({ trend }) {
  if (trend === "Improving") return <TrendingDown className="h-4 w-4 text-green-500" />;
  if (trend === "Worsening") return <TrendingUp className="h-4 w-4 text-red-500" />;
  return <Minus className="h-4 w-4 text-muted-foreground" />;
}

export function PaymentBehaviorCard({ behavior }) {
  if (!behavior) return null;

  const badgeClass = BEHAVIOR_COLORS[behavior.behavior_type] || "bg-muted text-foreground";
  const riskScore = behavior.behavior_risk_score || 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <UserCheck className="h-4 w-4 text-primary" />
          Payment Behavior Profile
        </CardTitle>
        <CardDescription>AI-classified payment personality</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Behavior type badge */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold ${badgeClass}`}>
            {behavior.behavior_type}
          </span>
          {behavior.nach_recommended && (
            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300">
              <Zap className="h-3 w-3" /> NACH Recommended
            </span>
          )}
        </div>

        {/* Key metrics grid */}
        <div className="grid grid-cols-3 gap-3">
          <div className="text-center p-3 rounded-lg bg-muted/50">
            <p className="text-xs text-muted-foreground mb-1">On-Time Ratio</p>
            <p className="text-xl font-bold text-foreground">{behavior.on_time_ratio?.toFixed(0)}%</p>
          </div>
          <div className="text-center p-3 rounded-lg bg-muted/50">
            <p className="text-xs text-muted-foreground mb-1">Avg Delay</p>
            <p className="text-xl font-bold text-foreground">{behavior.avg_delay_days?.toFixed(0)}d</p>
          </div>
          <div className="text-center p-3 rounded-lg bg-muted/50">
            <p className="text-xs text-muted-foreground mb-1">Trend</p>
            <div className="flex items-center justify-center gap-1 mt-1">
              <TrendIcon trend={behavior.trend} />
              <span className="text-sm font-medium text-foreground">{behavior.trend}</span>
            </div>
          </div>
        </div>

        {/* Payment style */}
        <div className="flex justify-between text-sm py-1 border-t border-border">
          <span className="text-muted-foreground">Payment Style</span>
          <span className="font-medium text-foreground">{behavior.payment_style}</span>
        </div>

        {/* Follow-up dependency */}
        <div className="flex justify-between text-sm py-1 border-t border-border">
          <span className="text-muted-foreground">Follow-up Dependency</span>
          <span className={`font-medium flex items-center gap-1 ${behavior.followup_dependency ? "text-amber-600 dark:text-amber-400" : "text-green-600 dark:text-green-400"}`}>
            {behavior.followup_dependency
              ? <><AlertCircle className="h-3 w-3" /> Yes — Requires Follow-up</>
              : <><CheckCircle className="h-3 w-3" /> No</>
            }
          </span>
        </div>

        {/* Behavior risk score gauge */}
        <div className="pt-1">
          <div className="flex justify-between text-xs text-muted-foreground mb-1.5">
            <span>Behavior Risk Score</span>
            <span className="font-semibold text-foreground">{riskScore}/100</span>
          </div>
          <div className="h-2.5 rounded-full bg-muted overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${RISK_GAUGE_COLOR(riskScore)}`}
              style={{ width: `${riskScore}%` }}
            />
          </div>
        </div>

        {/* Summary */}
        {behavior.behavior_summary && (
          <p className="text-xs text-muted-foreground leading-relaxed pt-1 border-t border-border">
            {behavior.behavior_summary}
          </p>
        )}

        <ExplainabilityPanel
          explanation={behavior.explanation}
          drivers={behavior.feature_drivers}
          title="Why This Behavior Was Predicted"
        />
      </CardContent>
    </Card>
  );
}
