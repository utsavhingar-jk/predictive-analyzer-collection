import {
  DollarSign,
  TrendingUp,
  AlertTriangle,
  Clock,
  Activity,
  ShieldAlert,
  Flame,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { PageLayout } from "@/components/layout/PageLayout";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { CashflowChart } from "@/components/charts/CashflowChart";
import { RiskPieChart } from "@/components/charts/RiskPieChart";
import { RiskBadge } from "@/components/dashboard/RiskBadge";
import { useDashboard } from "@/hooks/useDashboard";
import { formatCurrency, formatNumber, getPriorityColor } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function Skeleton({ className }) {
  return <div className={`animate-pulse rounded-lg bg-muted ${className}`} />;
}

const URGENCY_DOT = {
  Critical: "bg-red-500",
  High:     "bg-orange-500",
  Medium:   "bg-yellow-500",
  Low:      "bg-green-500",
};

export function ExecutiveDashboard() {
  const { summary, dso, cashflow, worklist, loading } = useDashboard();
  const navigate = useNavigate();

  const dsoTrendDir =
    dso?.dso_trend === "improving" ? "down" : dso?.dso_trend === "worsening" ? "up" : "neutral";

  // Top priority cases from API worklist
  const topCases = (worklist || []).slice(0, 5);

  return (
    <PageLayout
      title="Executive Dashboard"
      subtitle={`AI-powered AR intelligence · ${new Date().toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}`}
    >
      {/* KPI Row 1 — Core metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-32" />)
        ) : (
          <>
            <MetricCard
              title="Total Overdue"
              value={formatCurrency(summary?.overdue_amount || summary?.total_outstanding || 0)}
              subtitle={`${summary?.overdue_count || 0} invoices overdue`}
              icon={DollarSign}
              trend="up"
              trendLabel="Requires immediate attention"
            />
            <MetricCard
              title="Amount at Risk"
              value={formatCurrency(cashflow?.amount_at_risk || summary?.amount_at_risk || 0)}
              subtitle="Delay probability > 60%"
              icon={ShieldAlert}
              trend="up"
              trendLabel={cashflow?.shortfall_signal ? "⚠ Shortfall signal active" : "Within tolerance"}
            />
            <MetricCard
              title="Expected 30-Day Collections"
              value={formatCurrency(cashflow?.expected_30_day_collections || cashflow?.next_30_days_inflow || 0)}
              subtitle={`7-day: ${formatCurrency(cashflow?.expected_7_day_collections || cashflow?.next_7_days_inflow || 0)}`}
              icon={TrendingUp}
              trend="up"
              trendLabel="Predicted cash inflow"
            />
            <MetricCard
              title="High-Risk Invoices"
              value={formatNumber(summary?.high_risk_count || summary?.risk_breakdown?.High || 0)}
              subtitle={`of ${summary?.total_invoices || 0} total invoices`}
              icon={AlertTriangle}
              trend="down"
              trendLabel="Needs collector action"
            />
          </>
        )}
      </div>

      {/* KPI Row 2 — Supplementary signals */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)
        ) : (
          <>
            <MetricCard
              title="Predicted DSO"
              value={`${dso?.predicted_dso || 0}d`}
              subtitle={`Current: ${dso?.current_dso || 0}d · Benchmark: ${dso?.benchmark_dso || 45}d`}
              icon={Clock}
              trend={dsoTrendDir}
              trendLabel={`Trend: ${dso?.dso_trend || "stable"}`}
            />
            <MetricCard
              title="Overdue Carry-Forward"
              value={formatCurrency(cashflow?.overdue_carry_forward || 0)}
              subtitle="Expected uncollected in 30d"
              icon={Activity}
              trend="up"
              trendLabel="Based on delay probabilities"
            />
            <MetricCard
              title="Borrower Concentration"
              value={cashflow?.borrower_concentration_risk || "—"}
              subtitle="Top borrower % of outstanding"
              icon={Flame}
              trend={cashflow?.borrower_concentration_risk === "High" ? "up" : "neutral"}
              trendLabel="Concentration risk"
            />
            <MetricCard
              title="Total Outstanding"
              value={formatCurrency(summary?.total_outstanding || 0)}
              subtitle={`${summary?.total_invoices || 0} invoices in portfolio`}
              icon={DollarSign}
              trend="neutral"
              trendLabel="Full portfolio AR"
            />
          </>
        )}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {loading ? (
          <>
            <Skeleton className="col-span-2 h-96" />
            <Skeleton className="h-96" />
          </>
        ) : (
          <>
            <CashflowChart data={cashflow} />
            <RiskPieChart riskBreakdown={summary?.risk_breakdown} />
          </>
        )}
      </div>

      {/* Bottom Row — Portfolio Health + Top Priority Cases */}
      <div className="grid grid-cols-2 gap-4">
        {/* Portfolio Health */}
        {!loading && summary && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Activity className="h-4 w-4 text-primary" />
                Portfolio Health
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4 text-sm">
                {Object.entries(summary.risk_breakdown).map(([risk, count]) => (
                  <div key={risk} className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                    <div className="flex items-center gap-2">
                      <RiskBadge risk={risk} />
                    </div>
                    <span className="text-xl font-bold text-foreground">{count}</span>
                  </div>
                ))}
              </div>
              {cashflow?.shortfall_signal && (
                <div className="mt-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-300">
                  ⚠ <strong>Shortfall Signal:</strong> Expected 30-day collections are below 70% of total outstanding. Escalate high-priority cases immediately.
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Top Priority Cases */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Flame className="h-4 w-4 text-red-500" />
              Top Priority Cases
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="text-left px-4 py-2 text-xs text-muted-foreground font-semibold">#</th>
                  <th className="text-left px-4 py-2 text-xs text-muted-foreground font-semibold">Customer</th>
                  <th className="text-right px-4 py-2 text-xs text-muted-foreground font-semibold">Amount</th>
                  <th className="text-center px-4 py-2 text-xs text-muted-foreground font-semibold">Urgency</th>
                  <th className="text-left px-4 py-2 text-xs text-muted-foreground font-semibold">Action</th>
                </tr>
              </thead>
              <tbody>
                {topCases.map((inv, idx) => (
                  <tr
                    key={inv.invoice_id}
                    className="border-b border-border hover:bg-muted/20 transition-colors cursor-pointer"
                    onClick={() => navigate(`/invoices/${inv.invoice_id}`)}
                  >
                    <td className="px-4 py-2.5 text-muted-foreground font-mono text-xs">{idx + 1}</td>
                    <td className="px-4 py-2.5 font-medium text-foreground text-xs">
                      <div>{inv.customer_name}</div>
                      <div className="text-muted-foreground font-mono text-xs">{inv.invoice_id}</div>
                    </td>
                    <td className="px-4 py-2.5 text-right font-semibold text-foreground text-xs">
                      {formatCurrency(inv.amount)}
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <span className="flex items-center justify-center gap-1">
                        <span className={`w-2 h-2 rounded-full ${URGENCY_DOT[inv.urgency] || "bg-gray-400"}`} />
                        <span className={`text-xs font-semibold ${getPriorityColor(inv.urgency)}`}>
                          {inv.urgency}
                        </span>
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground max-w-[140px] truncate">
                      {inv.recommended_action}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>
    </PageLayout>
  );
}
