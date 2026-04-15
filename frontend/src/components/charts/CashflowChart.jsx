import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { formatCurrency } from "@/lib/utils";

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-card p-3 shadow-lg text-xs">
      <p className="font-semibold text-foreground mb-1">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2">
          <span style={{ color: p.color }}>●</span>
          <span className="text-muted-foreground">{p.name}:</span>
          <span className="font-medium text-foreground">{formatCurrency(p.value)}</span>
        </div>
      ))}
    </div>
  );
};

export function CashflowChart({ data }) {
  if (!data?.daily_breakdown) return null;

  const chartData = data.daily_breakdown.map((d) => ({
    date: d.date.slice(5), // MM-DD
    Predicted: Math.round(d.predicted_inflow),
    "Lower Bound": Math.round(d.lower_bound),
    "Upper Bound": Math.round(d.upper_bound),
  }));

  return (
    <Card className="col-span-2">
      <CardHeader>
        <CardTitle>30-Day Cash Flow Forecast</CardTitle>
        <CardDescription>
          Expected daily inflows with confidence bounds · 7-day:{" "}
          <strong>{formatCurrency(data.next_7_days_inflow)}</strong> · 30-day:{" "}
          <strong>{formatCurrency(data.next_30_days_inflow)}</strong>
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
            <defs>
              <linearGradient id="colorPredicted" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorUpper" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#22c55e" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} className="text-muted-foreground" />
            <YAxis tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 11 }} />
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            <Area
              type="monotone"
              dataKey="Upper Bound"
              stroke="#22c55e"
              strokeWidth={1}
              strokeDasharray="4 4"
              fill="url(#colorUpper)"
            />
            <Area
              type="monotone"
              dataKey="Predicted"
              stroke="#3b82f6"
              strokeWidth={2}
              fill="url(#colorPredicted)"
            />
            <Area
              type="monotone"
              dataKey="Lower Bound"
              stroke="#f59e0b"
              strokeWidth={1}
              strokeDasharray="4 4"
              fill="none"
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
