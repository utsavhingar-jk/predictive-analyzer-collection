import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Users,
  AlertOctagon,
  ExternalLink,
  TrendingDown,
  ShieldAlert,
  ChevronRight,
  Zap,
} from "lucide-react";
import { PageLayout } from "@/components/layout/PageLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RiskBadge } from "@/components/dashboard/RiskBadge";
import { api } from "@/lib/api";
import { formatCurrency, formatPct } from "@/lib/utils";

// ─── Subcomponents ────────────────────────────────────────────────────────────

function Skeleton({ className }) {
  return <div className={`animate-pulse rounded bg-muted ${className}`} />;
}

const SCORE_COLOR = (score) =>
  score >= 65 ? "text-red-600 dark:text-red-400"
  : score >= 35 ? "text-amber-600 dark:text-amber-400"
  : "text-green-600 dark:text-green-400";

const SCORE_BAR = (score) =>
  score >= 65 ? "bg-red-500" : score >= 35 ? "bg-amber-500" : "bg-green-500";

const RECOVERY_BAR = (rate) =>
  rate >= 0.7 ? "bg-green-500" : rate >= 0.4 ? "bg-amber-500" : "bg-red-500";

// ─── Borrower Detail Modal ────────────────────────────────────────────────────

function BorrowerDrawer({ borrower, onClose, navigate }) {
  if (!borrower) return null;
  const tier = borrower.borrower_risk_tier;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md bg-card border-l border-border h-full overflow-y-auto shadow-2xl p-6 space-y-5"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-bold text-foreground">{borrower.customer_name}</h2>
            <p className="text-sm text-muted-foreground">{borrower.industry} · Customer {borrower.customer_id}</p>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground text-xl font-bold">×</button>
        </div>

        {/* Risk summary */}
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 rounded-lg bg-muted/50">
            <p className="text-xs text-muted-foreground mb-1">Risk Score</p>
            <p className={`text-3xl font-black ${SCORE_COLOR(borrower.borrower_risk_score)}`}>
              {borrower.borrower_risk_score}<span className="text-sm font-normal text-muted-foreground">/100</span>
            </p>
          </div>
          <div className="p-3 rounded-lg bg-muted/50">
            <p className="text-xs text-muted-foreground mb-1">Risk Tier</p>
            <div className="mt-1"><RiskBadge risk={tier} /></div>
          </div>
        </div>

        {/* Exposure */}
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Exposure</p>
          {[
            ["Total Outstanding", formatCurrency(borrower.total_outstanding)],
            ["Overdue Invoices", `${borrower.overdue_invoice_count} invoice(s)`],
            ["Amount at Risk", formatCurrency(borrower.at_risk_amount)],
            ["Portfolio Share", `${borrower.concentration_pct?.toFixed(1)}%`],
          ].map(([label, value]) => (
            <div key={label} className="flex justify-between text-sm border-b border-border py-1.5">
              <span className="text-muted-foreground">{label}</span>
              <span className="font-medium text-foreground">{value}</span>
            </div>
          ))}
        </div>

        {/* Delay probability */}
        <div>
          <div className="flex justify-between text-sm mb-1.5">
            <span className="text-muted-foreground">Weighted Delay Probability</span>
            <span className="font-bold text-foreground">{formatPct(borrower.weighted_delay_probability)}</span>
          </div>
          <div className="h-2.5 rounded-full bg-muted overflow-hidden">
            <div
              className={`h-full rounded-full ${SCORE_BAR(borrower.borrower_risk_score)}`}
              style={{ width: `${Math.round(borrower.weighted_delay_probability * 100)}%` }}
            />
          </div>
        </div>

        {/* Recovery */}
        <div>
          <div className="flex justify-between text-sm mb-1.5">
            <span className="text-muted-foreground">Expected Recovery Rate</span>
            <span className="font-bold text-foreground">{formatPct(borrower.expected_recovery_rate)}</span>
          </div>
          <div className="h-2.5 rounded-full bg-muted overflow-hidden">
            <div
              className={`h-full rounded-full ${RECOVERY_BAR(borrower.expected_recovery_rate)}`}
              style={{ width: `${Math.round(borrower.expected_recovery_rate * 100)}%` }}
            />
          </div>
        </div>

        {/* Action */}
        <div className="p-3 rounded-lg bg-primary/10 border border-primary/20">
          <p className="text-xs text-muted-foreground mb-1">Relationship Action</p>
          <p className="text-sm font-semibold text-primary">{borrower.relationship_action}</p>
        </div>

        {/* Escalation */}
        {borrower.escalation_recommended && (
          <div className="flex items-center gap-2 p-2 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 text-sm">
            <AlertOctagon className="h-4 w-4" />
            <strong>Escalation Recommended</strong>
          </div>
        )}

        {/* View invoices */}
        <button
          onClick={() => { navigate(`/borrowers/${borrower.customer_id}`); onClose(); }}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors"
        >
          <ExternalLink className="h-4 w-4" />
          View Full Borrower Analysis
        </button>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

const TIER_OPTIONS = ["all", "High", "Medium", "Low"];

export function BorrowerPortfolio() {
  const navigate = useNavigate();
  const [borrowers, setBorrowers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tierFilter, setTierFilter] = useState("all");
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await api.getBorrowerPortfolio();
        if (!cancelled) setBorrowers(data);
      } catch {
        if (!cancelled) setBorrowers([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const filtered = tierFilter === "all"
    ? borrowers
    : borrowers.filter((b) => b.borrower_risk_tier === tierFilter);

  // Portfolio-level KPIs
  const totalExposure = borrowers.reduce((s, b) => s + b.total_outstanding, 0);
  const escalations = borrowers.filter((b) => b.escalation_recommended).length;
  const highRisk = borrowers.filter((b) => b.borrower_risk_tier === "High").length;
  const totalAtRisk = borrowers.reduce((s, b) => s + b.at_risk_amount, 0);

  return (
    <PageLayout
      title="Borrower Portfolio"
      subtitle="Borrower-level risk aggregation — ranked by risk score"
    >
      {/* KPI Row */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: "Total Exposure", value: formatCurrency(totalExposure), icon: Users, color: "text-foreground" },
          { label: "High-Risk Borrowers", value: highRisk, icon: ShieldAlert, color: "text-red-600 dark:text-red-400" },
          { label: "Amount at Risk", value: formatCurrency(totalAtRisk), icon: TrendingDown, color: "text-amber-600 dark:text-amber-400" },
          { label: "Escalations Required", value: escalations, icon: AlertOctagon, color: "text-red-600 dark:text-red-400" },
        ].map(({ label, value, icon: Icon, color }) => (
          <Card key={label}>
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">{label}</p>
                  <p className={`text-2xl font-black ${color}`}>{value}</p>
                </div>
                <Icon className={`h-6 w-6 ${color} opacity-60`} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Filter + count */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex items-center gap-1 border border-border rounded-md p-1">
          {TIER_OPTIONS.map((opt) => (
            <button
              key={opt}
              onClick={() => setTierFilter(opt)}
              className={`px-3 py-1 text-xs rounded font-medium transition-colors capitalize ${
                tierFilter === opt
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {opt}
            </button>
          ))}
        </div>
        <p className="text-sm text-muted-foreground ml-auto">
          {filtered.length} borrower{filtered.length !== 1 ? "s" : ""}
        </p>
      </div>

      {/* Borrower Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40">
                  <th className="text-left px-4 py-3 text-xs text-muted-foreground font-semibold">Rank</th>
                  <th className="text-left px-4 py-3 text-xs text-muted-foreground font-semibold">Borrower</th>
                  <th className="text-right px-4 py-3 text-xs text-muted-foreground font-semibold">Exposure</th>
                  <th className="text-center px-4 py-3 text-xs text-muted-foreground font-semibold">Risk Tier</th>
                  <th className="text-center px-4 py-3 text-xs text-muted-foreground font-semibold">Risk Score</th>
                  <th className="text-center px-4 py-3 text-xs text-muted-foreground font-semibold">Delay Prob.</th>
                  <th className="text-center px-4 py-3 text-xs text-muted-foreground font-semibold">Recovery</th>
                  <th className="text-right px-4 py-3 text-xs text-muted-foreground font-semibold">At Risk</th>
                  <th className="text-left px-4 py-3 text-xs text-muted-foreground font-semibold">Action</th>
                  <th className="text-center px-4 py-3 text-xs text-muted-foreground font-semibold">Escalate</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {loading
                  ? Array.from({ length: 5 }).map((_, i) => (
                      <tr key={i} className="border-b border-border">
                        {Array.from({ length: 11 }).map((__, j) => (
                          <td key={j} className="px-4 py-3"><Skeleton className="h-4 w-full" /></td>
                        ))}
                      </tr>
                    ))
                  : filtered.map((b, idx) => (
                      <tr
                        key={b.customer_id}
                        className="border-b border-border hover:bg-muted/30 transition-colors cursor-pointer"
                        onClick={() => setSelected(b)}
                      >
                        {/* Rank */}
                        <td className="px-4 py-3">
                          <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-muted text-xs font-bold text-foreground">
                            {idx + 1}
                          </span>
                        </td>

                        {/* Borrower */}
                        <td className="px-4 py-3">
                          <p className="font-semibold text-foreground text-sm">{b.customer_name}</p>
                          <p className="text-xs text-muted-foreground">{b.industry}</p>
                        </td>

                        {/* Exposure */}
                        <td className="px-4 py-3 text-right">
                          <p className="font-semibold text-foreground">{formatCurrency(b.total_outstanding)}</p>
                          <p className="text-xs text-muted-foreground">{b.concentration_pct?.toFixed(1)}% of portfolio</p>
                        </td>

                        {/* Risk Tier */}
                        <td className="px-4 py-3 text-center">
                          <RiskBadge risk={b.borrower_risk_tier} />
                        </td>

                        {/* Risk Score bar */}
                        <td className="px-4 py-3 text-center min-w-[100px]">
                          <div className="flex items-center gap-2">
                            <span className={`font-bold text-sm w-8 text-right ${SCORE_COLOR(b.borrower_risk_score)}`}>
                              {b.borrower_risk_score}
                            </span>
                            <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                              <div
                                className={`h-full rounded-full ${SCORE_BAR(b.borrower_risk_score)}`}
                                style={{ width: `${b.borrower_risk_score}%` }}
                              />
                            </div>
                          </div>
                        </td>

                        {/* Delay probability */}
                        <td className="px-4 py-3 text-center">
                          <span className={`font-semibold text-sm ${
                            b.weighted_delay_probability > 0.6 ? "text-red-600 dark:text-red-400"
                            : b.weighted_delay_probability > 0.3 ? "text-amber-600 dark:text-amber-400"
                            : "text-green-600 dark:text-green-400"
                          }`}>
                            {formatPct(b.weighted_delay_probability)}
                          </span>
                        </td>

                        {/* Recovery rate */}
                        <td className="px-4 py-3 text-center min-w-[100px]">
                          <div className="flex items-center gap-2">
                            <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                              <div
                                className={`h-full rounded-full ${RECOVERY_BAR(b.expected_recovery_rate)}`}
                                style={{ width: `${Math.round(b.expected_recovery_rate * 100)}%` }}
                              />
                            </div>
                            <span className="text-xs font-medium text-foreground w-9 text-left">
                              {formatPct(b.expected_recovery_rate)}
                            </span>
                          </div>
                        </td>

                        {/* At risk */}
                        <td className="px-4 py-3 text-right">
                          {b.at_risk_amount > 0
                            ? <span className="text-red-600 dark:text-red-400 font-semibold text-sm">{formatCurrency(b.at_risk_amount)}</span>
                            : <span className="text-muted-foreground text-sm">—</span>
                          }
                        </td>

                        {/* Action */}
                        <td className="px-4 py-3 max-w-[180px]">
                          <span className="text-xs text-muted-foreground truncate block">{b.relationship_action}</span>
                        </td>

                        {/* Escalate */}
                        <td className="px-4 py-3 text-center">
                          {b.escalation_recommended
                            ? <AlertOctagon className="h-4 w-4 text-red-500 mx-auto" />
                            : <span className="text-xs text-muted-foreground">—</span>
                          }
                        </td>

                        {/* Detail */}
                        <td className="px-4 py-3">
                          <ChevronRight className="h-4 w-4 text-muted-foreground" />
                        </td>
                      </tr>
                    ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Drawer */}
      {selected && (
        <BorrowerDrawer
          borrower={selected}
          onClose={() => setSelected(null)}
          navigate={navigate}
        />
      )}
    </PageLayout>
  );
}
