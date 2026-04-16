/**
 * Sentinel Watchlist — customers flagged by the external signals engine.
 * Displays AI-detected external risk indicators per borrower.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Radio, AlertOctagon, Newspaper, UserX,
  Mail, TrendingDown, ChevronRight, ShieldAlert, Eye,
} from "lucide-react";
import { PageLayout } from "@/components/layout/PageLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { mockWatchlist } from "@/lib/mockData";

// ── Signal type metadata ──────────────────────────────────────────────────────

const SIGNAL_META = {
  leadership_change: {
    icon: UserX,
    label: "Leadership Change",
    color: "text-orange-600 dark:text-orange-400",
    bg: "bg-orange-100 dark:bg-orange-900/30 border-orange-200 dark:border-orange-800",
  },
  news_alert: {
    icon: Newspaper,
    label: "News Alert",
    color: "text-red-600 dark:text-red-400",
    bg: "bg-red-100 dark:bg-red-900/30 border-red-200 dark:border-red-800",
  },
  email_anomaly: {
    icon: Mail,
    label: "Email Anomaly",
    color: "text-yellow-600 dark:text-yellow-500",
    bg: "bg-yellow-100 dark:bg-yellow-900/30 border-yellow-200 dark:border-yellow-800",
  },
  ap_contact_failure: {
    icon: AlertOctagon,
    label: "AP Contact Failure",
    color: "text-red-700 dark:text-red-400",
    bg: "bg-red-100 dark:bg-red-900/30 border-red-300 dark:border-red-700",
  },
  sector_news: {
    icon: TrendingDown,
    label: "Sector Stress",
    color: "text-amber-600 dark:text-amber-400",
    bg: "bg-amber-100 dark:bg-amber-900/30 border-amber-200 dark:border-amber-800",
  },
};

const DEFAULT_SIGNAL_META = {
  icon: AlertOctagon,
  label: "External Signal",
  color: "text-muted-foreground",
  bg: "bg-muted/50 border-border",
};

const RISK_LEVEL_STYLE = {
  Critical: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300 border-red-200 dark:border-red-800",
  High: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300 border-orange-200 dark:border-orange-800",
  Medium: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300 border-yellow-200 dark:border-yellow-800",
  Clear: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300 border-green-200 dark:border-green-800",
};

function Skeleton({ className }) {
  return <div className={`animate-pulse rounded bg-muted ${className}`} />;
}

// ── Signal badge ──────────────────────────────────────────────────────────────

function SignalBadge({ signal }) {
  const meta = SIGNAL_META[signal.signal_type] || DEFAULT_SIGNAL_META;
  const Icon = meta.icon;
  return (
    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border font-medium ${meta.bg} ${meta.color}`}>
      <Icon className="h-2.5 w-2.5" />
      {meta.label}
    </span>
  );
}

// ── Expandable customer row ───────────────────────────────────────────────────

function WatchlistRow({ customer, navigate }) {
  const [expanded, setExpanded] = useState(false);
  const levelStyle = RISK_LEVEL_STYLE[customer.risk_level] || RISK_LEVEL_STYLE.Medium;

  // Score color
  const scoreColor =
    customer.overall_sentinel_score >= 80 ? "text-red-600 dark:text-red-400"
    : customer.overall_sentinel_score >= 50 ? "text-orange-600 dark:text-orange-400"
    : "text-amber-600 dark:text-amber-400";

  return (
    <>
      <tr
        className="border-b border-border hover:bg-muted/20 cursor-pointer transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        {/* Sentinel score */}
        <td className="px-4 py-3 text-center">
          <span className={`text-lg font-black ${scoreColor}`}>{customer.overall_sentinel_score}</span>
          <p className="text-xs text-muted-foreground">/100</p>
        </td>

        {/* Customer */}
        <td className="px-4 py-3">
          <p className="font-semibold text-sm text-foreground">{customer.customer_name}</p>
          <p className="text-xs text-muted-foreground">{customer.industry} · ID {customer.customer_id}</p>
        </td>

        {/* Risk level */}
        <td className="px-4 py-3 text-center">
          <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${levelStyle}`}>
            {customer.risk_level}
          </span>
        </td>

        {/* Signal count */}
        <td className="px-4 py-3 text-center">
          <div className="flex items-center justify-center gap-2">
            {customer.high_signal_count > 0 && (
              <span className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400 font-semibold">
                <AlertOctagon className="h-3 w-3" />
                {customer.high_signal_count} High
              </span>
            )}
            {customer.medium_signal_count > 0 && (
              <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">
                {customer.medium_signal_count} Med
              </span>
            )}
          </div>
        </td>

        {/* Signal type badges */}
        <td className="px-4 py-3">
          <div className="flex flex-wrap gap-1">
            {customer.signals.slice(0, 2).map((s, i) => (
              <SignalBadge key={i} signal={s} />
            ))}
            {customer.signals.length > 2 && (
              <span className="text-xs text-muted-foreground">+{customer.signals.length - 2} more</span>
            )}
          </div>
        </td>

        {/* Last checked */}
        <td className="px-4 py-3 text-xs text-muted-foreground">{customer.last_checked}</td>

        {/* Actions */}
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            <button
              onClick={(e) => { e.stopPropagation(); navigate(`/invoices/INV-2024-001`); }}
              className="text-xs px-2.5 py-1 rounded border border-primary/30 text-primary hover:bg-primary/10 transition-colors font-medium"
            >
              View Invoices
            </button>
            <ChevronRight className={`h-4 w-4 text-muted-foreground transition-transform ${expanded ? "rotate-90" : ""}`} />
          </div>
        </td>
      </tr>

      {/* Expanded signal details */}
      {expanded && (
        <tr className="border-b border-border bg-muted/10">
          <td colSpan={7} className="px-6 py-4">
            <div className="space-y-3">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                Detected Signals
              </p>
              {customer.signals.map((signal, i) => {
                const meta = SIGNAL_META[signal.signal_type] || DEFAULT_SIGNAL_META;
                const Icon = meta.icon;
                return (
                  <div key={i} className={`flex items-start gap-3 p-3 rounded-lg border ${meta.bg}`}>
                    <div className={`w-7 h-7 rounded-lg bg-background/80 flex items-center justify-center shrink-0`}>
                      <Icon className={`h-3.5 w-3.5 ${meta.color}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className={`text-xs font-semibold ${meta.color}`}>{meta.label}</span>
                        <span className={`text-xs px-1.5 py-0.5 rounded border ${
                          signal.severity === "High"
                            ? "bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800"
                            : signal.severity === "Medium"
                            ? "bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-800"
                            : "bg-green-100 text-green-700 border-green-200"
                        }`}>{signal.severity}</span>
                        <span className="text-xs text-muted-foreground ml-auto">{signal.source}</span>
                      </div>
                      <p className="text-sm text-foreground">{signal.description}</p>
                    </div>
                  </div>
                );
              })}

              {/* Recommendation */}
              <div className="mt-3 p-3 rounded-lg bg-primary/10 border border-primary/20">
                <p className="text-xs font-semibold text-primary mb-1">Sentinel Recommendation</p>
                <p className="text-sm text-foreground">{customer.recommendation}</p>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function Watchlist() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getWatchlist()
      .then(setData)
      .catch(() => setData(mockWatchlist))
      .finally(() => setLoading(false));
  }, []);

  const criticalCount = data?.critical_count ?? 0;
  const highCount = data?.high_count ?? 0;
  const totalFlagged = data?.total_flagged ?? 0;
  const customers = data?.customers ?? [];

  return (
    <PageLayout
      title="Sentinel Watchlist"
      subtitle="AI-monitored external risk signals — leadership, news, AP contact, and email anomalies"
    >
      {/* KPI row */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          {
            label: "Total Flagged",
            value: loading ? "—" : totalFlagged,
            icon: Radio,
            color: "text-foreground",
            bg: "bg-primary/10 border-primary/20",
          },
          {
            label: "Critical Risk",
            value: loading ? "—" : criticalCount,
            icon: AlertOctagon,
            color: "text-red-600 dark:text-red-400",
            bg: "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800",
          },
          {
            label: "High Risk",
            value: loading ? "—" : highCount,
            icon: ShieldAlert,
            color: "text-orange-600 dark:text-orange-400",
            bg: "bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-800",
          },
          {
            label: "Signal Types",
            value: "5 monitored",
            icon: Eye,
            color: "text-blue-600 dark:text-blue-400",
            bg: "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800",
          },
        ].map(({ label, value, icon: Icon, color, bg }) => (
          <Card key={label} className={`border ${bg}`}>
            <CardContent className="p-5 flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground mb-1">{label}</p>
                <p className={`text-2xl font-black ${color}`}>{value}</p>
              </div>
              <Icon className={`h-6 w-6 ${color} opacity-60`} />
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Signal type legend */}
      <div className="flex flex-wrap items-center gap-2 mb-4 p-3 rounded-xl bg-muted/30 border border-border">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mr-1">Signals:</span>
        {Object.entries(SIGNAL_META).map(([key, meta]) => {
          const Icon = meta.icon;
          return (
            <span key={key} className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${meta.bg} ${meta.color}`}>
              <Icon className="h-2.5 w-2.5" />
              {meta.label}
            </span>
          );
        })}
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40">
                  <th className="text-center px-4 py-3 text-xs text-muted-foreground font-semibold">Score</th>
                  <th className="text-left px-4 py-3 text-xs text-muted-foreground font-semibold">Customer</th>
                  <th className="text-center px-4 py-3 text-xs text-muted-foreground font-semibold">Level</th>
                  <th className="text-center px-4 py-3 text-xs text-muted-foreground font-semibold">Signals</th>
                  <th className="text-left px-4 py-3 text-xs text-muted-foreground font-semibold">Signal Types</th>
                  <th className="text-left px-4 py-3 text-xs text-muted-foreground font-semibold">Last Checked</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {loading
                  ? Array.from({ length: 4 }).map((_, i) => (
                      <tr key={i} className="border-b border-border">
                        {Array.from({ length: 7 }).map((__, j) => (
                          <td key={j} className="px-4 py-3">
                            <Skeleton className="h-4 w-full" />
                          </td>
                        ))}
                      </tr>
                    ))
                  : customers.map((c) => (
                      <WatchlistRow key={c.customer_id} customer={c} navigate={navigate} />
                    ))}
              </tbody>
            </table>

            {!loading && customers.length === 0 && (
              <div className="py-16 text-center">
                <Radio className="h-8 w-8 text-muted-foreground mx-auto mb-3 opacity-40" />
                <p className="text-sm text-muted-foreground">No customers on watchlist</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </PageLayout>
  );
}
