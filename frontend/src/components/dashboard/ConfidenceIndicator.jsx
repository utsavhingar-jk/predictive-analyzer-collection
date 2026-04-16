/**
 * ConfidenceIndicator — shows prediction confidence, evidence score,
 * missing data indicators, and fallback flag for a delay prediction.
 */

import { ShieldCheck, ShieldAlert, AlertCircle, Database, Cpu } from "lucide-react";

function ConfidenceBar({ value, color }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-700 ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-bold text-foreground w-8 text-right">{pct}%</span>
    </div>
  );
}

const MISSING_DATA_LABEL = {
  behavior_type: "Payment behavior profile",
  on_time_ratio: "On-time payment ratio",
  avg_delay_days_historical: "Historical delay data",
  behavior_risk_score: "Behavior risk score",
  deterioration_trend: "Payment trend signal",
  followup_dependency: "Follow-up dependency flag",
};

export function ConfidenceIndicator({ prediction, learningBoost = 0 }) {
  if (!prediction) return null;

  const rawConfidence = prediction.confidence ?? 0.70;
  const confidence = Math.min(1.0, rawConfidence + (learningBoost ?? 0));
  const evidenceScore = prediction.evidence_score ?? 0.50;
  const missing = prediction.missing_data_indicators ?? [];
  const usedFallback = prediction.used_fallback ?? false;

  const confColor = confidence >= 0.75 ? "bg-green-500"
    : confidence >= 0.55 ? "bg-amber-500"
    : "bg-red-400";

  const evColor = evidenceScore >= 0.75 ? "bg-blue-500"
    : evidenceScore >= 0.50 ? "bg-amber-500"
    : "bg-red-400";

  const confLabel = confidence >= 0.75 ? "High confidence"
    : confidence >= 0.55 ? "Moderate confidence"
    : "Low confidence";

  return (
    <div className="rounded-xl border border-border bg-muted/20 p-3 space-y-3">
      {/* Header */}
      <div className="flex items-center gap-2">
        {confidence >= 0.70
          ? <ShieldCheck className="h-4 w-4 text-green-500" />
          : <ShieldAlert className="h-4 w-4 text-amber-500" />
        }
        <p className="text-xs font-semibold text-foreground">Prediction Confidence</p>
        {usedFallback && (
          <span className="ml-auto flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-800">
            <Cpu className="h-2.5 w-2.5" />
            Rule Fallback
          </span>
        )}
      </div>

      {/* Confidence bars */}
      <div className="space-y-2">
        <div>
          <div className="flex justify-between text-xs text-muted-foreground mb-1">
            <span>Model Confidence</span>
            <span className={confidence >= 0.75 ? "text-green-600 dark:text-green-400" : confidence >= 0.55 ? "text-amber-600 dark:text-amber-400" : "text-red-500"}>
              {confLabel}
            </span>
          </div>
          <ConfidenceBar value={confidence} color={confColor} />
        </div>

        <div>
          <div className="flex justify-between text-xs text-muted-foreground mb-1">
            <span className="flex items-center gap-1"><Database className="h-3 w-3" /> Evidence Score</span>
            <span>{missing.length === 0 ? "Complete" : `${missing.length} field${missing.length !== 1 ? "s" : ""} missing`}</span>
          </div>
          <ConfidenceBar value={evidenceScore} color={evColor} />
        </div>
      </div>

      {/* Learning boost from interaction history */}
      {learningBoost > 0 && (
        <div className="flex items-center gap-2 text-xs text-green-600 dark:text-green-400">
          <Database className="h-3 w-3" />
          <span>+{Math.round(learningBoost * 100)}% boost from interaction history</span>
        </div>
      )}

      {/* Missing data indicators */}
      {missing.length > 0 && (
        <div className="pt-1 border-t border-border/50">
          <p className="text-xs font-semibold text-muted-foreground mb-1.5 flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />
            Missing Enrichment Data
          </p>
          <div className="flex flex-wrap gap-1.5">
            {missing.map((field) => (
              <span
                key={field}
                className="text-xs px-2 py-0.5 rounded-full bg-muted border border-border text-muted-foreground"
              >
                {MISSING_DATA_LABEL[field] || field}
              </span>
            ))}
          </div>
          <p className="text-xs text-muted-foreground mt-1.5">
            Provide these signals to increase prediction confidence.
          </p>
        </div>
      )}
    </div>
  );
}
