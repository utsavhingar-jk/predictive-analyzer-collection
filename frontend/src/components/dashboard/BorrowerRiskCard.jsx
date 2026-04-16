/**
 * BorrowerRiskCard
 *
 * Compact card showing borrower-level risk summary:
 * - Risk score gauge
 * - Weighted delay probability
 * - Expected recovery rate
 * - Escalation flag
 * - Relationship action
 */

import { Users, TrendingDown, AlertOctagon, ShieldCheck } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ExplainabilityPanel } from "@/components/dashboard/ExplainabilityPanel";
import { formatCurrency, formatPct } from "@/lib/utils";

const TIER_COLORS = {
  High:   "text-red-600 dark:text-red-400",
  Medium: "text-amber-600 dark:text-amber-400",
  Low:    "text-green-600 dark:text-green-400",
};

const TIER_BG = {
  High:   "bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800",
  Medium: "bg-amber-50 border-amber-200 dark:bg-amber-900/20 dark:border-amber-800",
  Low:    "bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800",
};

const SCORE_BAR_COLOR = (score) =>
  score >= 65 ? "bg-red-500" : score >= 35 ? "bg-amber-500" : "bg-green-500";

const RECOVERY_COLOR = (rate) =>
  rate >= 0.7 ? "bg-green-500" : rate >= 0.4 ? "bg-amber-500" : "bg-red-500";

function StatRow({ label, value, highlight }) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-border last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={`text-sm font-semibold ${highlight || "text-foreground"}`}>{value}</span>
    </div>
  );
}

export function BorrowerRiskCard({ borrower }) {
  if (!borrower) return null;

  const tier = borrower.borrower_risk_tier || "Medium";
  const score = borrower.borrower_risk_score || 0;
  const recoveryRate = borrower.expected_recovery_rate || 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Users className="h-4 w-4 text-primary" />
          Borrower Risk Profile
        </CardTitle>
        <CardDescription>Aggregated across all open invoices</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Risk score + tier */}
        <div className={`flex items-center justify-between p-3 rounded-lg border ${TIER_BG[tier]}`}>
          <div>
            <p className="text-xs text-muted-foreground mb-0.5">Borrower Risk Score</p>
            <p className="text-3xl font-black text-foreground">
              {score}<span className="text-sm font-normal text-muted-foreground">/100</span>
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs text-muted-foreground mb-0.5">Risk Tier</p>
            <p className={`text-2xl font-bold ${TIER_COLORS[tier]}`}>{tier}</p>
          </div>
        </div>

        {/* Score bar */}
        <div className="h-2 rounded-full bg-muted overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-700 ${SCORE_BAR_COLOR(score)}`}
            style={{ width: `${score}%` }}
          />
        </div>

        {/* Key stats */}
        <div className="space-y-0">
          <StatRow
            label="Total Outstanding"
            value={formatCurrency(borrower.total_outstanding)}
          />
          <StatRow
            label="Overdue Invoices"
            value={`${borrower.overdue_invoice_count} of ${borrower.open_invoice_count}`}
            highlight={borrower.overdue_invoice_count > 0 ? "text-red-600 dark:text-red-400" : "text-foreground"}
          />
          <StatRow
            label="Weighted Delay Probability"
            value={formatPct(borrower.weighted_delay_probability)}
            highlight={borrower.weighted_delay_probability > 0.6 ? "text-red-600 dark:text-red-400" : "text-foreground"}
          />
          <StatRow
            label="Portfolio Concentration"
            value={`${borrower.concentration_pct?.toFixed(1)}%`}
            highlight={borrower.concentration_pct > 20 ? "text-amber-600 dark:text-amber-400" : "text-foreground"}
          />
          <StatRow
            label="Borrower DSO"
            value={`${borrower.borrower_dso}d`}
            highlight={
              borrower.dso_vs_portfolio === "Worse"
                ? "text-red-600 dark:text-red-400"
                : borrower.dso_vs_portfolio === "Better"
                ? "text-green-600 dark:text-green-400"
                : "text-foreground"
            }
          />
        </div>

        {/* Recovery rate bar */}
        <div>
          <div className="flex justify-between text-xs text-muted-foreground mb-1">
            <span>Expected Recovery Rate</span>
            <span className="font-semibold text-foreground">
              {formatPct(recoveryRate)} ({formatCurrency(borrower.expected_recovery_amount)})
            </span>
          </div>
          <div className="h-2.5 rounded-full bg-muted overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${RECOVERY_COLOR(recoveryRate)}`}
              style={{ width: `${Math.round(recoveryRate * 100)}%` }}
            />
          </div>
        </div>

        {/* At-risk amount */}
        {borrower.at_risk_amount > 0 && (
          <div className="flex items-center gap-2 p-2 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 text-xs">
            <TrendingDown className="h-3.5 w-3.5 shrink-0" />
            <span><strong>{formatCurrency(borrower.at_risk_amount)}</strong> at risk (delay prob &gt;60%)</span>
          </div>
        )}

        {/* Relationship action */}
        <div className="p-3 rounded-lg bg-primary/10 border border-primary/20">
          <p className="text-xs text-muted-foreground mb-1">Relationship Action</p>
          <p className="text-sm font-semibold text-primary">{borrower.relationship_action}</p>
        </div>

        {/* Escalation badge */}
        {borrower.escalation_recommended ? (
          <div className="flex items-center gap-2 text-xs font-medium text-red-600 dark:text-red-400">
            <AlertOctagon className="h-3.5 w-3.5" />
            Escalation recommended
          </div>
        ) : (
          <div className="flex items-center gap-2 text-xs font-medium text-green-600 dark:text-green-400">
            <ShieldCheck className="h-3.5 w-3.5" />
            No escalation required
          </div>
        )}

        {/* Summary */}
        {borrower.borrower_summary && (
          <p className="text-xs text-muted-foreground leading-relaxed border-t border-border pt-2">
            {borrower.borrower_summary}
          </p>
        )}

        <ExplainabilityPanel
          explanation={borrower.explanation}
          drivers={borrower.feature_drivers}
          title="Why Borrower Risk Looks Like This"
        />
      </CardContent>
    </Card>
  );
}
