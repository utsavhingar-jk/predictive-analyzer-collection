import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-lg border border-border bg-card p-3 shadow-lg text-xs space-y-1">
      <p className="font-semibold text-foreground">{d.feature_name}</p>
      <p className="text-muted-foreground">
        Value: <span className="text-foreground font-medium">{d.feature_value}</span>
      </p>
      <p className="text-muted-foreground">
        SHAP: <span className="font-medium" style={{ color: d.shap_value >= 0 ? "#ef4444" : "#22c55e" }}>
          {d.shap_value >= 0 ? "+" : ""}{d.shap_value.toFixed(3)}
        </span>
      </p>
      <p className="text-muted-foreground">
        Impact:{" "}
        <span className={d.impact === "negative" ? "text-red-500" : "text-green-500"}>
          {d.impact === "negative" ? "↑ Risk" : "↓ Risk"}
        </span>
      </p>
    </div>
  );
};

export function ShapBarChart({ explanation }) {
  if (!explanation?.top_features) return null;

  const data = [...explanation.top_features].sort((a, b) => b.shap_value - a.shap_value);

  return (
    <Card>
      <CardHeader>
        <CardTitle>SHAP Feature Importance</CardTitle>
        <CardDescription>
          Why the model predicted this outcome · base value:{" "}
          <strong>{explanation.base_value?.toFixed(2)}</strong> → prediction:{" "}
          <strong>{explanation.prediction_value?.toFixed(2)}</strong>
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={data} layout="vertical" margin={{ left: 40, right: 16 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" horizontal={false} />
            <XAxis type="number" tickFormatter={(v) => v.toFixed(2)} tick={{ fontSize: 11 }} />
            <YAxis
              type="category"
              dataKey="feature_name"
              tick={{ fontSize: 11 }}
              width={130}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine x={0} stroke="hsl(var(--border))" />
            <Bar dataKey="shap_value" radius={[0, 4, 4, 0]}>
              {data.map((entry, i) => (
                <Cell
                  key={i}
                  fill={entry.shap_value >= 0 ? "#ef4444" : "#22c55e"}
                  fillOpacity={0.85}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
