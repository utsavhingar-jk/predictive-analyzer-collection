import { useNavigate } from "react-router-dom";
import { Search, Filter, ArrowUpDown, ExternalLink } from "lucide-react";
import { PageLayout } from "@/components/layout/PageLayout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { RiskBadge } from "@/components/dashboard/RiskBadge";
import { useWorklist } from "@/hooks/useWorklist";
import { formatCurrency, formatPct, getPriorityColor } from "@/lib/utils";

function Skeleton({ className }) {
  return <div className={`animate-pulse rounded bg-muted ${className}`} />;
}

const RISK_OPTIONS = ["all", "High", "Medium", "Low"];

export function CollectorWorklist() {
  const navigate = useNavigate();
  const { worklist, loading, search, setSearch, riskFilter, setRiskFilter } = useWorklist();

  return (
    <PageLayout
      title="Collector Worklist"
      subtitle="Priority-sorted invoices — highest impact opportunities first"
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
                  <th className="text-left px-4 py-3 font-semibold text-muted-foreground">#</th>
                  <th className="text-left px-4 py-3 font-semibold text-muted-foreground">Invoice</th>
                  <th className="text-left px-4 py-3 font-semibold text-muted-foreground">Customer</th>
                  <th className="text-right px-4 py-3 font-semibold text-muted-foreground">Amount</th>
                  <th className="text-center px-4 py-3 font-semibold text-muted-foreground">Days OD</th>
                  <th className="text-center px-4 py-3 font-semibold text-muted-foreground">Risk</th>
                  <th className="text-right px-4 py-3 font-semibold text-muted-foreground">Priority Score</th>
                  <th className="text-left px-4 py-3 font-semibold text-muted-foreground">Recommended Action</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {loading
                  ? Array.from({ length: 6 }).map((_, i) => (
                      <tr key={i} className="border-b border-border">
                        {Array.from({ length: 9 }).map((__, j) => (
                          <td key={j} className="px-4 py-3">
                            <Skeleton className="h-4 w-full" />
                          </td>
                        ))}
                      </tr>
                    ))
                  : worklist.map((inv, idx) => (
                      <tr
                        key={inv.invoice_id}
                        className="border-b border-border hover:bg-muted/30 transition-colors cursor-pointer"
                        onClick={() => navigate(`/invoices/${inv.invoice_id}`)}
                      >
                        <td className="px-4 py-3 text-muted-foreground font-mono text-xs">
                          {idx + 1}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-primary font-semibold">
                          {inv.invoice_id}
                        </td>
                        <td className="px-4 py-3 font-medium text-foreground">
                          {inv.customer_name}
                        </td>
                        <td className="px-4 py-3 text-right font-semibold text-foreground">
                          {formatCurrency(inv.amount)}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span
                            className={`font-medium ${
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
                        <td className="px-4 py-3 text-center">
                          <RiskBadge risk={inv.risk_label} />
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="font-bold text-foreground">
                            {formatCurrency(inv.priority_score)}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {formatPct(inv.delay_probability)} delay prob.
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`text-xs font-medium ${getPriorityColor(
                              inv.priority_score > 50000 ? "Critical" :
                              inv.priority_score > 20000 ? "High" :
                              inv.priority_score > 5000 ? "Medium" : "Low"
                            )}`}
                          >
                            {inv.recommended_action || "Review Required"}
                          </span>
                        </td>
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
                    ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </PageLayout>
  );
}
