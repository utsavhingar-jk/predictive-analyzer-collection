import {
  DollarSign,
  TrendingUp,
  AlertTriangle,
  Clock,
  Activity,
} from "lucide-react";
import { PageLayout } from "@/components/layout/PageLayout";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { CashflowChart } from "@/components/charts/CashflowChart";
import { RiskPieChart } from "@/components/charts/RiskPieChart";
import { useDashboard } from "@/hooks/useDashboard";
import { formatCurrency, formatNumber } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RiskBadge } from "@/components/dashboard/RiskBadge";

function Skeleton({ className }) {
  return <div className={`animate-pulse rounded-lg bg-muted ${className}`} />;
}

export function ExecutiveDashboard() {
  const { summary, dso, cashflow, loading } = useDashboard();

  const dsoTrendDir =
    dso?.dso_trend === "improving" ? "down" : dso?.dso_trend === "worsening" ? "up" : "neutral";

  return (
    <PageLayout
      title="Executive Dashboard"
      subtitle={`AI-powered AR overview · ${new Date().toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}`}
    >
      {/* KPI Metrics Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-32" />)
        ) : (
          <>
            <MetricCard
              title="Total Outstanding"
              value={formatCurrency(summary?.total_outstanding || 0)}
              subtitle={`${summary?.overdue_count || 0} invoices overdue`}
              icon={DollarSign}
              trend="up"
              trendLabel="Requires attention"
            />
            <MetricCard
              title="7-Day Cash Inflow"
              value={formatCurrency(cashflow?.next_7_days_inflow || 0)}
              subtitle="Predicted cash inflow"
              icon={TrendingUp}
              trend="up"
              trendLabel={`30-day: ${formatCurrency(cashflow?.next_30_days_inflow || 0)}`}
            />
            <MetricCard
              title="Predicted DSO"
              value={`${dso?.predicted_dso || 0}d`}
              subtitle={`Current: ${dso?.current_dso || 0}d · Benchmark: ${dso?.benchmark_dso || 45}d`}
              icon={Clock}
              trend={dsoTrendDir}
              trendLabel={`Trend: ${dso?.dso_trend || "stable"}`}
            />
            <MetricCard
              title="High Risk Invoices"
              value={formatNumber(summary?.risk_breakdown?.High || 0)}
              subtitle={`of ${summary?.total_invoices || 0} total invoices`}
              icon={AlertTriangle}
              trend="down"
              trendLabel="Immediate action needed"
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

      {/* Portfolio Health Summary */}
      {!loading && summary && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-primary" />
              Portfolio Health Summary
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-6 text-sm">
              {Object.entries(summary.risk_breakdown).map(([risk, count]) => (
                <div key={risk} className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                  <div className="flex items-center gap-2">
                    <RiskBadge risk={risk} />
                    <span className="text-muted-foreground">Risk Invoices</span>
                  </div>
                  <span className="text-xl font-bold text-foreground">{count}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </PageLayout>
  );
}
