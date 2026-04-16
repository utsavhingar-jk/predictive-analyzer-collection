/**
 * SentinelAlert — inline component showing external risk signals on Invoice Detail.
 */

import { useState, useEffect } from "react";
import { Radio, AlertOctagon, Newspaper, UserX, Mail, TrendingDown, ChevronDown, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";

const SIGNAL_META = {
  leadership_change: { icon: UserX,       label: "Leadership Change", color: "text-orange-600 dark:text-orange-400", dot: "bg-orange-500" },
  news_alert:        { icon: Newspaper,   label: "News Alert",        color: "text-red-600 dark:text-red-400",       dot: "bg-red-500" },
  email_anomaly:     { icon: Mail,        label: "Email Anomaly",     color: "text-yellow-600 dark:text-yellow-500", dot: "bg-yellow-500" },
  ap_contact_failure:{ icon: AlertOctagon,label: "AP Contact Failure",color: "text-red-700 dark:text-red-400",       dot: "bg-red-600" },
  sector_news:       { icon: TrendingDown,label: "Sector Stress",     color: "text-amber-600 dark:text-amber-400",   dot: "bg-amber-500" },
};

const SEV_BADGE = {
  High:   "bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800",
  Medium: "bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-800",
  Low:    "bg-green-100 text-green-700 border-green-200",
};

export function SentinelAlert({ customerId }) {
  const [data, setData] = useState(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!customerId) return;
    api.getSentinelCheck(String(customerId))
      .then(setData)
      .catch(() => {});
  }, [customerId]);

  if (!data || !data.is_flagged) return null;

  const criticalOrHigh = data.risk_level === "Critical" || data.risk_level === "High";

  return (
    <div className={`rounded-xl border overflow-hidden ${
      data.risk_level === "Critical"
        ? "border-red-400/50 bg-gradient-to-br from-red-500/8 to-red-500/3"
        : "border-orange-400/40 bg-gradient-to-br from-orange-500/8 to-orange-500/3"
    }`}>
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
      >
        <div className={`relative w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
          criticalOrHigh ? "bg-red-100 dark:bg-red-900/30" : "bg-amber-100 dark:bg-amber-900/30"
        }`}>
          <Radio className={`h-4 w-4 ${criticalOrHigh ? "text-red-600 dark:text-red-400" : "text-amber-600 dark:text-amber-400"} animate-pulse`} />
          <span className={`absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full ${criticalOrHigh ? "bg-red-500" : "bg-amber-500"} animate-ping`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className={`text-sm font-bold ${criticalOrHigh ? "text-red-700 dark:text-red-300" : "text-amber-700 dark:text-amber-300"}`}>
              Sentinel Alert — {data.risk_level} Risk
            </p>
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${
              data.risk_level === "Critical"
                ? "bg-red-100 text-red-700 border-red-200 dark:bg-red-900/40 dark:text-red-300 dark:border-red-800"
                : "bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-900/40 dark:text-orange-300 dark:border-orange-800"
            }`}>{data.overall_sentinel_score}/100</span>
          </div>
          <p className="text-xs text-muted-foreground">{data.signals.length} external signal{data.signals.length !== 1 ? "s" : ""} detected · {data.last_checked}</p>
        </div>
        {expanded ? <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" /> : <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />}
      </button>

      {/* Expanded signals */}
      {expanded && (
        <div className="px-4 pb-4 space-y-2 border-t border-border/50 pt-3">
          {data.signals.map((signal, i) => {
            const meta = SIGNAL_META[signal.signal_type] || { icon: AlertOctagon, label: "Signal", color: "text-muted-foreground", dot: "bg-muted-foreground" };
            const Icon = meta.icon;
            return (
              <div key={i} className="flex items-start gap-2.5 text-sm">
                <div className={`w-1.5 h-1.5 rounded-full mt-2 shrink-0 ${meta.dot}`} />
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                    <Icon className={`h-3.5 w-3.5 ${meta.color} shrink-0`} />
                    <span className={`text-xs font-medium ${meta.color}`}>{meta.label}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded border ${SEV_BADGE[signal.severity] || SEV_BADGE.Low}`}>{signal.severity}</span>
                    <span className="text-xs text-muted-foreground ml-auto">via {signal.source}</span>
                  </div>
                  <p className="text-xs text-foreground/80 leading-relaxed">{signal.description}</p>
                </div>
              </div>
            );
          })}

          <div className="mt-3 pt-2 border-t border-border/40">
            <p className="text-xs font-semibold text-muted-foreground mb-1">Sentinel Recommendation</p>
            <p className="text-xs text-foreground">{data.recommendation}</p>
          </div>
        </div>
      )}
    </div>
  );
}
