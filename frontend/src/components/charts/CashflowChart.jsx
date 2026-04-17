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
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { formatCurrency } from "@/lib/utils";

const BAR_COLORS = ["#3b82f6", "#22c55e", "#f59e0b"];

const formatCompactCurrency = (value) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    notation: "compact",
    minimumFractionDigits: 0,
    maximumFractionDigits: 1,
  }).format(value);

const sumRange = (rows, key, end) =>
  rows.slice(0, end).reduce((total, row) => total + (Number(row?.[key]) || 0), 0);

const buildHorizonData = (data) => {
  const daily = data.daily_breakdown || [];
  const cumulativePredicted = [
    Number(data.next_7_days_inflow) || 0,
    Number(data.next_15_days_inflow) || 0,
    Number(data.next_30_days_inflow) || 0,
  ];
  const cumulativeLower = [
    sumRange(daily, "lower_bound", 7),
    sumRange(daily, "lower_bound", 15),
    sumRange(daily, "lower_bound", 30),
  ];
  const cumulativeUpper = [
    sumRange(daily, "upper_bound", 7),
    sumRange(daily, "upper_bound", 15),
    sumRange(daily, "upper_bound", 30),
  ];

  return [
    {
      horizon: "Days 0-7",
      predicted: cumulativePredicted[0],
      lower: cumulativeLower[0],
      upper: cumulativeUpper[0],
      cumulative: cumulativePredicted[0],
    },
    {
      horizon: "Days 8-15",
      predicted: Math.max(0, cumulativePredicted[1] - cumulativePredicted[0]),
      lower: Math.max(0, cumulativeLower[1] - cumulativeLower[0]),
      upper: Math.max(0, cumulativeUpper[1] - cumulativeUpper[0]),
      cumulative: cumulativePredicted[1],
    },
    {
      horizon: "Days 16-30",
      predicted: Math.max(0, cumulativePredicted[2] - cumulativePredicted[1]),
      lower: Math.max(0, cumulativeLower[2] - cumulativeLower[1]),
      upper: Math.max(0, cumulativeUpper[2] - cumulativeUpper[1]),
      cumulative: cumulativePredicted[2],
    },
  ];
};

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;

  const point = payload[0]?.payload;
  if (!point) return null;

  return (
    <div className="rounded-lg border border-border bg-card p-3 shadow-lg text-xs">
      <p className="font-semibold text-foreground mb-1">{point.horizon}</p>
      <div className="space-y-1">
        <div className="flex items-center justify-between gap-4">
          <span className="text-muted-foreground">Incremental forecast</span>
          <span className="font-medium text-foreground">{formatCurrency(point.predicted)}</span>
        </div>
        <div className="flex items-center justify-between gap-4">
          <span className="text-muted-foreground">Confidence range</span>
          <span className="font-medium text-foreground">
            {formatCurrency(point.lower)} - {formatCurrency(point.upper)}
          </span>
        </div>
        <div className="flex items-center justify-between gap-4">
          <span className="text-muted-foreground">Cumulative by horizon</span>
          <span className="font-medium text-foreground">{formatCurrency(point.cumulative)}</span>
        </div>
      </div>
    </div>
  );
};

export function CashflowChart({ data }) {
  if (!data?.daily_breakdown) return null;

  const chartData = buildHorizonData(data);

  return (
    <Card className="col-span-2">
      <CardHeader>
        <CardTitle>30-Day Cash Flow Forecast</CardTitle>
        <CardDescription>
          Horizon contributions derived from cumulative forecasts · 7-day:{" "}
          <strong>{formatCurrency(data.next_7_days_inflow)}</strong> · 15-day:{" "}
          <strong>{formatCurrency(data.next_15_days_inflow)}</strong> · 30-day:{" "}
          <strong>{formatCurrency(data.next_30_days_inflow)}</strong>
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" vertical={false} />
            <XAxis dataKey="horizon" tick={{ fontSize: 11 }} className="text-muted-foreground" />
            <YAxis tickFormatter={(v) => formatCompactCurrency(v)} tick={{ fontSize: 11 }} />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(148, 163, 184, 0.08)" }} />
            <Bar dataKey="predicted" radius={[8, 8, 0, 0]}>
              {chartData.map((entry, index) => (
                <Cell key={entry.horizon} fill={BAR_COLORS[index % BAR_COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
