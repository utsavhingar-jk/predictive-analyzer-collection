import { useState, useCallback, useEffect } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { FlaskConical, TrendingUp, TrendingDown, Minus, RefreshCw } from "lucide-react";
import { PageLayout } from "@/components/layout/PageLayout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

function ImpactCard({ label, baseline, predicted, unit = "", invert = false }) {
  const diff = predicted - baseline;
  const isPositive = invert ? diff < 0 : diff > 0;
  const isNeutral = Math.abs(diff) < 0.1;
  const Icon = isNeutral ? Minus : isPositive ? TrendingUp : TrendingDown;
  const color = isNeutral
    ? "text-muted-foreground"
    : isPositive
    ? "text-green-600 dark:text-green-400"
    : "text-red-600 dark:text-red-400";

  return (
    <Card>
      <CardContent className="p-5">
        <p className="text-sm text-muted-foreground mb-1">{label}</p>
        <p className="text-2xl font-bold text-foreground">
          {typeof predicted === "number" && unit === "$"
            ? formatCurrency(predicted)
            : `${predicted?.toFixed(1)}${unit}`}
        </p>
        <div className={`flex items-center gap-1 text-xs mt-1 ${color}`}>
          <Icon className="h-3.5 w-3.5" />
          <span>
            {isNeutral ? "No change" :
             `${isPositive ? "+" : ""}${diff.toFixed(1)}${unit} vs baseline`}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

export function ScenarioSimulator() {
  const [efficiency, setEfficiency] = useState(0);
  const [discount, setDiscount] = useState(0);
  const [delay, setDelay] = useState(0);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadBaseline = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.simulateWhatIf({
        recovery_improvement_pct: 0,
        discount_pct: 0,
        delay_followup_days: 0,
      });
      setResult(data);
    } catch (err) {
      setResult(null);
      setError(err?.message || "Failed to load scenario baseline.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBaseline();
  }, [loadBaseline]);

  const runSimulation = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.simulateWhatIf({
        recovery_improvement_pct: efficiency,
        discount_pct: discount,
        delay_followup_days: delay,
      });
      setResult(data);
    } catch (err) {
      setError(err?.message || "Failed to run simulation.");
    } finally {
      setLoading(false);
    }
  }, [efficiency, discount, delay]);

  const safe = result || {
    predicted_recovery_pct: 0,
    cashflow_shift: 0,
    dso_shift: 0,
    baseline_recovery_pct: 0,
    baseline_cashflow: 0,
    baseline_dso: 0,
    scenario_summary: "",
  };

  const compareData = [
    {
      metric: "Recovery %",
      Baseline: safe.baseline_recovery_pct,
      Scenario: safe.predicted_recovery_pct,
    },
  ];

  const cashflowDelta = safe.cashflow_shift;
  const dsoDelta = safe.dso_shift;

  return (
    <PageLayout
      title="Scenario Simulator"
      subtitle="Model the impact of collection strategy changes on key AR metrics"
    >
      <div className="grid grid-cols-3 gap-6">
        {/* Sliders Panel */}
        <Card className="col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FlaskConical className="h-4 w-4 text-primary" />
              Strategy Levers
            </CardTitle>
            <CardDescription>Adjust the levers and run the simulation</CardDescription>
          </CardHeader>
          <CardContent className="space-y-7">
            <Slider
              label="Collection Efficiency Improvement"
              value={efficiency}
              onChange={setEfficiency}
              min={0}
              max={50}
              step={1}
              suffix="%"
            />
            <Slider
              label="Early Payment Discount Offered"
              value={discount}
              onChange={setDiscount}
              min={0}
              max={20}
              step={0.5}
              suffix="%"
            />
            <Slider
              label="Follow-up Timing Shift"
              value={delay}
              onChange={setDelay}
              min={-14}
              max={14}
              step={1}
              suffix=" days"
            />

            <div className="text-xs text-muted-foreground p-3 rounded-lg bg-muted/50 space-y-1">
              <p><strong>Efficiency:</strong> % improvement in collector throughput</p>
              <p><strong>Discount:</strong> Early-pay discount offered to customers</p>
              <p><strong>Timing:</strong> Negative = contact customers earlier</p>
            </div>

            <Button
              className="w-full gap-2"
              onClick={runSimulation}
              disabled={loading}
            >
              {loading ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <FlaskConical className="h-4 w-4" />
              )}
              {loading ? "Simulating…" : "Run Simulation"}
            </Button>

            <Button
              variant="outline"
              className="w-full"
              onClick={() => {
                setEfficiency(0);
                setDiscount(0);
                setDelay(0);
                loadBaseline();
              }}
            >
              Reset to Baseline
            </Button>
          </CardContent>
        </Card>

        {/* Results Panel */}
        <div className="col-span-2 space-y-4">
          {/* Scenario Summary */}
          {safe.scenario_summary && (
            <Card className="border-primary/40 bg-primary/5">
              <CardContent className="p-4">
                <p className="text-sm font-medium text-primary">{safe.scenario_summary}</p>
              </CardContent>
            </Card>
          )}
          {error && (
            <Card className="border-red-500/40 bg-red-500/5">
              <CardContent className="p-4">
                <p className="text-sm font-medium text-red-600 dark:text-red-400">{error}</p>
              </CardContent>
            </Card>
          )}

          {/* Impact Cards */}
          <div className="grid grid-cols-3 gap-4">
            <ImpactCard
              label="Recovery Rate"
              baseline={safe.baseline_recovery_pct}
              predicted={safe.predicted_recovery_pct}
              unit="%"
            />
            <ImpactCard
              label="30-Day Cashflow Impact"
              baseline={safe.baseline_cashflow}
              predicted={safe.baseline_cashflow + cashflowDelta}
              unit="$"
            />
            <ImpactCard
              label="DSO Impact"
              baseline={safe.baseline_dso}
              predicted={safe.baseline_dso + dsoDelta}
              unit=" days"
              invert={true}
            />
          </div>

          {/* Bar Chart Comparison */}
          <Card>
            <CardHeader>
              <CardTitle>Recovery Rate Comparison</CardTitle>
              <CardDescription>Baseline vs. projected scenario outcome</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart
                  data={compareData}
                  margin={{ top: 8, right: 16, bottom: 8, left: 8 }}
                  barCategoryGap="40%"
                >
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" vertical={false} />
                  <XAxis dataKey="metric" tick={{ fontSize: 12 }} />
                  <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v) => [`${v.toFixed(1)}%`]} />
                  <Bar dataKey="Baseline" radius={[4, 4, 0, 0]}>
                    <Cell fill="#94a3b8" />
                  </Bar>
                  <Bar dataKey="Scenario" radius={[4, 4, 0, 0]}>
                    <Cell
                      fill={
                        safe.predicted_recovery_pct > safe.baseline_recovery_pct
                          ? "#22c55e"
                          : "#ef4444"
                      }
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Detailed Metrics Table */}
          <Card>
            <CardHeader>
              <CardTitle>Detailed Impact Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-muted-foreground">
                    <th className="text-left py-2 font-medium">Metric</th>
                    <th className="text-right py-2 font-medium">Baseline</th>
                    <th className="text-right py-2 font-medium">Scenario</th>
                    <th className="text-right py-2 font-medium">Change</th>
                  </tr>
                </thead>
                <tbody className="text-foreground">
                  <tr className="border-b border-border">
                    <td className="py-2.5">Recovery Rate</td>
                    <td className="text-right py-2.5">{safe.baseline_recovery_pct.toFixed(1)}%</td>
                    <td className="text-right py-2.5">{safe.predicted_recovery_pct.toFixed(1)}%</td>
                    <td className={`text-right py-2.5 font-semibold ${safe.predicted_recovery_pct > safe.baseline_recovery_pct ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                      {safe.predicted_recovery_pct > safe.baseline_recovery_pct ? "+" : ""}
                      {(safe.predicted_recovery_pct - safe.baseline_recovery_pct).toFixed(1)}%
                    </td>
                  </tr>
                  <tr className="border-b border-border">
                    <td className="py-2.5">30-Day Cashflow</td>
                    <td className="text-right py-2.5">{formatCurrency(safe.baseline_cashflow)}</td>
                    <td className="text-right py-2.5">{formatCurrency(safe.baseline_cashflow + cashflowDelta)}</td>
                    <td className={`text-right py-2.5 font-semibold ${cashflowDelta >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                      {cashflowDelta >= 0 ? "+" : ""}{formatCurrency(cashflowDelta)}
                    </td>
                  </tr>
                  <tr>
                    <td className="py-2.5">Days Sales Outstanding</td>
                    <td className="text-right py-2.5">{safe.baseline_dso.toFixed(1)}d</td>
                    <td className="text-right py-2.5">{(safe.baseline_dso + dsoDelta).toFixed(1)}d</td>
                    <td className={`text-right py-2.5 font-semibold ${dsoDelta <= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                      {dsoDelta <= 0 ? "" : "+"}{dsoDelta.toFixed(1)}d
                    </td>
                  </tr>
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      </div>
    </PageLayout>
  );
}
