/**
 * DelayPredictionCard
 *
 * Displays the enhanced delay prediction output:
 * - Delay probability gauge
 * - Risk score + risk tier
 * - Top human-readable drivers
 */

import { AlertTriangle, ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ExplainabilityPanel } from "@/components/dashboard/ExplainabilityPanel";

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

const PROB_COLOR = (p) => {
  if (p >= 0.65) return "bg-red-500";
  if (p >= 0.35) return "bg-amber-500";
  return "bg-green-500";
};

export function DelayPredictionCard({ prediction }) {
  if (!prediction) return null;

  const prob = prediction.delay_probability || 0;
  const probPct = Math.round(prob * 100);
  const tier = prediction.risk_tier || "Medium";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-primary" />
          Delay Prediction
        </CardTitle>
        <CardDescription>Enriched delay risk with behavior signals</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Probability bar */}
        <div>
          <div className="flex justify-between text-sm mb-1.5">
            <span className="text-muted-foreground">Delay Probability</span>
            <span className="font-bold text-foreground">{probPct}%</span>
          </div>
          <div className="h-3 rounded-full bg-muted overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${PROB_COLOR(prob)}`}
              style={{ width: `${probPct}%` }}
            />
          </div>
        </div>

        {/* Risk score + tier */}
        <div className={`flex items-center justify-between p-3 rounded-lg border ${TIER_BG[tier]}`}>
          <div>
            <p className="text-xs text-muted-foreground">Risk Score</p>
            <p className="text-2xl font-black text-foreground">{prediction.risk_score}<span className="text-sm font-normal text-muted-foreground">/100</span></p>
          </div>
          <div className="text-right">
            <p className="text-xs text-muted-foreground">Risk Tier</p>
            <p className={`text-xl font-bold ${TIER_COLORS[tier]}`}>{tier}</p>
          </div>
        </div>

        {/* Top drivers */}
        {prediction.top_drivers?.length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground font-semibold mb-2 uppercase tracking-wide">Top Risk Drivers</p>
            <ul className="space-y-1.5">
              {prediction.top_drivers.slice(0, 4).map((driver, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-foreground">
                  <ChevronRight className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
                  <span>{driver}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <ExplainabilityPanel
          explanation={prediction.explanation}
          drivers={prediction.feature_drivers}
          title="Why Delay Risk Looks Like This"
        />

        <p className="text-xs text-muted-foreground border-t border-border pt-2">
          Model: <span className="font-mono">{prediction.model_version}</span>
        </p>
      </CardContent>
    </Card>
  );
}
