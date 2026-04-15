import { useNavigate } from "react-router-dom";
import { Search, ExternalLink, Zap } from "lucide-react";
import { PageLayout } from "@/components/layout/PageLayout";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { RiskBadge } from "@/components/dashboard/RiskBadge";
import { useWorklist } from "@/hooks/useWorklist";
import { formatCurrency, formatPct, getPriorityColor } from "@/lib/utils";

function Skeleton({ className }) {
  return <div className={`animate-pulse rounded bg-muted ${className}`} />;
}

const RISK_OPTIONS = ["all", "High", "Medium", "Low"];

const URGENCY_BADGE = {
  Critical: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  High:     "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
  Medium:   "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300",
  Low:      "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
};

const BEHAVIOR_BADGE = {
  "Consistent Payer":       "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
  "Occasional Late Payer":  "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300",
  "Reminder Driven Payer":  "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
  "Partial Payment Payer":  "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  "Chronic Delayed Payer":  "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  "High Risk Defaulter":    "bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-300",
};

export function CollectorWorklist() {
  const navigate = useNavigate();
  const { worklist, loading, search, setSearch, riskFilter, setRiskFilter } = useWorklist();

  return (
    <PageLayout
      title="Collector Worklist"
      subtitle="AI-prioritized invoices — ranked by delay risk × invoice amount"
    >
      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by customer or invoice ID…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex items-center gap-1 border border-border rounded-md p-1">
          {RISK_OPTIONS.map((opt) => (
            <button
              key={opt}
              onClick={() => setRiskFilter(opt)}
              className={`px-3 py-1 text-xs rounded font-medium transition-colors capitalize ${
                riskFilter === opt
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {opt}
            </button>
          ))}
        </div>
        <p className="text-sm text-muted-foreground ml-auto">
          {worklist.length} invoice{worklist.length !== 1 ? "s" : ""}
        </p>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40">
                  <th className="text-left px-4 py-3 font-semibold text-muted-foreground text-xs">Rank</th>
                  <th className="text-left px-4 py-3 font-semibold text-muted-foreground text-xs">Invoice</th>
                  <th className="text-left px-4 py-3 font-semibold text-muted-foreground text-xs">Customer</th>
                  <th className="text-right px-4 py-3 font-semibold text-muted-foreground text-xs">Amount</th>
                  <th className="text-center px-4 py-3 font-semibold text-muted-foreground text-xs">DPD</th>
                  <th className="text-center px-4 py-3 font-semibold text-muted-foreground text-xs">Risk Tier</th>
                  <th className="text-left px-4 py-3 font-semibold text-muted-foreground text-xs">Behavior</th>
                  <th className="text-center px-4 py-3 font-semibold text-muted-foreground text-xs">Priority</th>
                  <th className="text-left px-4 py-3 font-semibold text-muted-foreground text-xs">Action</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {loading
                  ? Array.from({ length: 6 }).map((_, i) => (
                      <tr key={i} className="border-b border-border">
                        {Array.from({ length: 10 }).map((__, j) => (
                          <td key={j} className="px-4 py-3">
                            <Skeleton className="h-4 w-full" />
                          </td>
                        ))}
                      </tr>
                    ))
                  : worklist.map((inv, idx) => {
                      const urgencyClass = URGENCY_BADGE[inv.urgency] || URGENCY_BADGE.Medium;
                      const behaviorClass = BEHAVIOR_BADGE[inv.behavior_type] || "bg-muted text-foreground";
                      return (
                        <tr
                          key={inv.invoice_id}
                          className="border-b border-border hover:bg-muted/30 transition-colors cursor-pointer"
                          onClick={() => navigate(`/invoices/${inv.invoice_id}`)}
                        >
                          {/* Rank */}
                          <td className="px-4 py-3">
                            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-muted text-xs font-bold text-foreground">
                              {inv.priority_rank || idx + 1}
                            </span>
                          </td>

                          {/* Invoice ID */}
                          <td className="px-4 py-3 font-mono text-xs text-primary font-semibold">
                            {inv.invoice_id}
                          </td>

                          {/* Customer */}
                          <td className="px-4 py-3 font-medium text-foreground">
                            {inv.customer_name}
                          </td>

                          {/* Amount */}
                          <td className="px-4 py-3 text-right font-semibold text-foreground">
                            {formatCurrency(inv.amount)}
                          </td>

                          {/* DPD */}
                          <td className="px-4 py-3 text-center">
                            <span
                              className={`font-semibold text-xs ${
                                inv.days_overdue > 60
                                  ? "text-red-600 dark:text-red-400"
                                  : inv.days_overdue > 30
                                  ? "text-amber-600 dark:text-amber-400"
                                  : inv.days_overdue > 0
                                  ? "text-orange-500"
                                  : "text-muted-foreground"
                              }`}
                            >
                              {inv.days_overdue > 0 ? `+${inv.days_overdue}d` : "Current"}
                            </span>
                          </td>

                          {/* Risk Tier */}
                          <td className="px-4 py-3 text-center">
                            <RiskBadge risk={inv.risk_tier || inv.risk_label} />
                          </td>

                          {/* Behavior badge */}
                          <td className="px-4 py-3">
                            <div className="flex flex-col gap-1">
                              {inv.behavior_type && (
                                <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${behaviorClass}`}>
                                  {inv.behavior_type}
                                </span>
                              )}
                              {inv.nach_recommended && (
                                <span className="inline-flex items-center gap-0.5 text-xs text-blue-600 dark:text-blue-400">
                                  <Zap className="h-3 w-3" /> NACH
                                </span>
                              )}
                            </div>
                          </td>

                          {/* Priority score */}
                          <td className="px-4 py-3 text-center">
                            <div className="font-bold text-foreground text-lg leading-tight">
                              {inv.priority_score}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {formatPct(inv.delay_probability)} delay
                            </div>
                          </td>

                          {/* Recommended action */}
                          <td className="px-4 py-3">
                            <div className="flex flex-col gap-1">
                              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${urgencyClass}`}>
                                {inv.urgency || "—"}
                              </span>
                              <span className="text-xs text-muted-foreground truncate max-w-[160px]">
                                {inv.recommended_action || "Review Required"}
                              </span>
                            </div>
                          </td>

                          {/* Deep dive link */}
                          <td className="px-4 py-3">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate(`/invoices/${inv.invoice_id}`);
                              }}
                            >
                              <ExternalLink className="h-4 w-4" />
                            </Button>
                          </td>
                        </tr>
                      );
                    })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </PageLayout>
  );
}
