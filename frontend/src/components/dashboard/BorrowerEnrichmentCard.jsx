/**
 * BorrowerEnrichmentCard — displays CredCheck enrichment signals:
 * MCA compliance, GST filing health, EPFO stability, bureau/credit health, legal profile.
 */

import { useState, useEffect } from "react";
import {
  Building2, FileText, Users, CreditCard, Scale,
  CheckCircle2, AlertTriangle, XCircle, Database, ChevronDown, ChevronRight,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

function ScorePill({ score, size = "md" }) {
  const color = score >= 70 ? "text-green-700 bg-green-100 border-green-200 dark:bg-green-900/30 dark:text-green-300 dark:border-green-800"
    : score >= 45 ? "text-amber-700 bg-amber-100 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-800"
    : "text-red-700 bg-red-100 border-red-200 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800";
  return (
    <span className={`inline-block font-bold border rounded px-1.5 py-0.5 ${size === "lg" ? "text-base" : "text-xs"} ${color}`}>
      {score}
    </span>
  );
}

function DataFlag({ label, available }) {
  return (
    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border font-medium ${
      available
        ? "bg-green-50 text-green-700 border-green-200 dark:bg-green-900/20 dark:text-green-300 dark:border-green-800"
        : "bg-muted text-muted-foreground border-border"
    }`}>
      {available ? <CheckCircle2 className="h-2.5 w-2.5" /> : <XCircle className="h-2.5 w-2.5 opacity-40" />}
      {label}
    </span>
  );
}

function Section({ icon: Icon, title, children, color = "text-primary" }) {
  return (
    <div className="space-y-1.5">
      <div className={`flex items-center gap-1.5 text-xs font-semibold ${color} uppercase tracking-wide`}>
        <Icon className="h-3 w-3" />
        {title}
      </div>
      {children}
    </div>
  );
}

const STATUS_COLOR = {
  "Active":              "text-green-600 dark:text-green-400",
  "Strike-off Notice":   "text-red-600 dark:text-red-400",
  "Inactive":            "text-muted-foreground",
  "Strong":              "text-green-600 dark:text-green-400",
  "Moderate":            "text-amber-600 dark:text-amber-400",
  "Weak":                "text-orange-600 dark:text-orange-400",
  "Distressed":          "text-red-600 dark:text-red-400",
  "Clean":               "text-green-600 dark:text-green-400",
  "Minor":               "text-amber-600 dark:text-amber-400",
  "Significant":         "text-orange-600 dark:text-orange-400",
  "Critical":            "text-red-600 dark:text-red-400",
  "Current":             "text-green-600 dark:text-green-400",
  "1-30 days late":      "text-amber-600 dark:text-amber-400",
  "31-90 days late":     "text-orange-600 dark:text-orange-400",
  "Defaulter":           "text-red-600 dark:text-red-400",
  "Suspended":           "text-red-600 dark:text-red-400",
};

export function BorrowerEnrichmentCard({ customerId }) {
  const [data, setData] = useState(null);
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!customerId) return;
    api.getBorrowerEnrichment(String(customerId))
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [customerId]);

  if (loading || !data) return null;

  const hasCriticalFlags = data.risk_flags.length > 0;
  const scoreColor = data.enrichment_score >= 70 ? "text-green-600 dark:text-green-400"
    : data.enrichment_score >= 45 ? "text-amber-600 dark:text-amber-400"
    : "text-red-600 dark:text-red-400";

  return (
    <Card className={`border ${hasCriticalFlags ? "border-orange-300/50 dark:border-orange-800/50" : "border-border"}`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left hover:bg-muted/20 transition-colors"
      >
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Database className="h-4 w-4 text-primary" />
            CredCheck Enrichment
            <span className={`ml-auto text-lg font-black ${scoreColor}`}>{data.enrichment_score}</span>
            <span className="text-xs text-muted-foreground">/100</span>
            <span className={`text-xs font-medium px-2 py-0.5 rounded border ${
              data.enrichment_label === "Data-Rich" ? "bg-green-100 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-300 dark:border-green-800"
              : data.enrichment_label === "Moderate" ? "bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-800"
              : "bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800"
            }`}>{data.enrichment_label}</span>
            {expanded ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
          </CardTitle>
        </CardHeader>
      </button>

      {/* Always visible: data availability flags + risk flags */}
      <CardContent className="pt-0 pb-3">
        {/* Data availability flags */}
        <div className="flex flex-wrap gap-1.5 mb-3">
          <DataFlag label="Bureau" available={data.data_availability.has_bureau_data} />
          <DataFlag label="GST" available={data.data_availability.has_gst_data} />
          <DataFlag label="Legal" available={data.data_availability.has_legal_data} />
          <DataFlag label="MCA" available={data.data_availability.has_mca_data} />
          <DataFlag label="EPFO" available={data.data_availability.has_epfo_data} />
          <DataFlag label="Digitap" available={data.data_availability.has_digitap_data} />
        </div>

        {/* Risk flags */}
        {data.risk_flags.length > 0 && (
          <div className="space-y-1 mb-3">
            {data.risk_flags.map((flag, i) => (
              <div key={i} className="flex items-center gap-2 text-xs text-orange-700 dark:text-orange-400">
                <AlertTriangle className="h-3 w-3 shrink-0" />
                {flag}
              </div>
            ))}
          </div>
        )}

        {/* Expandable detailed sections */}
        {expanded && (
          <div className="space-y-4 pt-2 border-t border-border">

            {/* MCA */}
            <Section icon={Building2} title="MCA Compliance" color={data.mca.compliance_score < 50 ? "text-red-600 dark:text-red-400" : "text-foreground"}>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                <span className="text-muted-foreground">Status</span>
                <span className={`font-medium ${STATUS_COLOR[data.mca.mca_status] || ""}`}>{data.mca.mca_status}</span>
                <span className="text-muted-foreground">Compliance Score</span>
                <ScorePill score={data.mca.compliance_score} />
                <span className="text-muted-foreground">Last Filing</span>
                <span className="font-medium">{data.mca.last_filing_date || "—"}</span>
                {data.mca.flag && <>
                  <span className="text-muted-foreground">Flag</span>
                  <span className="font-medium text-red-600 dark:text-red-400">{data.mca.flag}</span>
                </>}
              </div>
            </Section>

            {/* GST */}
            <Section icon={FileText} title="GST Filing Health">
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                <span className="text-muted-foreground">Filing Score</span>
                <ScorePill score={data.gst.filing_score} />
                <span className="text-muted-foreground">Delay Band</span>
                <span className={`font-medium ${STATUS_COLOR[data.gst.delay_band] || ""}`}>{data.gst.delay_band}</span>
                <span className="text-muted-foreground">Turnover Band</span>
                <span className="font-medium">{data.gst.avg_turnover_band || "—"}</span>
                <span className="text-muted-foreground">ITC Health</span>
                <span className={`font-medium ${data.gst.itc_health === "Healthy" ? "text-green-600 dark:text-green-400" : data.gst.itc_health === "Mismatch Risk" ? "text-amber-600 dark:text-amber-400" : "text-muted-foreground"}`}>
                  {data.gst.itc_health || "Unknown"}
                </span>
              </div>
            </Section>

            {/* Bureau */}
            <Section icon={CreditCard} title="Bureau / Credit Health">
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                <span className="text-muted-foreground">Health</span>
                <span className={`font-medium ${STATUS_COLOR[data.bureau.credit_health_label] || ""}`}>{data.bureau.credit_health_label}</span>
                {data.bureau.bureau_score && <>
                  <span className="text-muted-foreground">CIBIL Score</span>
                  <span className="font-semibold">{data.bureau.bureau_score}</span>
                </>}
                <span className="text-muted-foreground">DPD Class</span>
                <span className={`font-medium ${["Doubtful", "Loss"].includes(data.bureau.dpd_classification) ? "text-red-600 dark:text-red-400" : data.bureau.dpd_classification === "Sub-standard" ? "text-amber-600 dark:text-amber-400" : "text-green-600 dark:text-green-400"}`}>
                  {data.bureau.dpd_classification}
                </span>
                <span className="text-muted-foreground">Overdue Loans</span>
                <span className={`font-medium ${data.bureau.overdue_count > 2 ? "text-red-500" : "text-foreground"}`}>{data.bureau.overdue_count}</span>
                <span className="text-muted-foreground">Cheque Dishonour</span>
                <span className={`font-medium ${data.bureau.cheque_dishonour_count > 1 ? "text-red-500" : "text-foreground"}`}>{data.bureau.cheque_dishonour_count}</span>
              </div>
            </Section>

            {/* Legal */}
            <Section icon={Scale} title="Legal Profile">
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                <span className="text-muted-foreground">Legal Risk</span>
                <span className={`font-medium ${STATUS_COLOR[data.legal.legal_risk_label] || ""}`}>{data.legal.legal_risk_label}</span>
                <span className="text-muted-foreground">Active Suits</span>
                <span className={`font-medium ${data.legal.active_suits > 0 ? "text-red-500" : "text-foreground"}`}>{data.legal.active_suits}</span>
                {data.legal.nclt_risk && <>
                  <span className="text-muted-foreground">NCLT Risk</span>
                  <span className="font-medium text-red-600 dark:text-red-400">Yes — insolvency risk</span>
                </>}
              </div>
            </Section>

            {/* EPFO */}
            {data.epfo.epfo_registered && (
              <Section icon={Users} title="EPFO Stability">
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                  {data.epfo.employee_count && <>
                    <span className="text-muted-foreground">Employee Count</span>
                    <span className="font-medium">{data.epfo.employee_count.toLocaleString("en-IN")}</span>
                  </>}
                  <span className="text-muted-foreground">PF Trend</span>
                  <span className={`font-medium ${data.epfo.pf_trend === "Growing" ? "text-green-600 dark:text-green-400" : data.epfo.pf_trend === "Declining" ? "text-red-500" : "text-foreground"}`}>
                    {data.epfo.pf_trend}
                  </span>
                  <span className="text-muted-foreground">Stability Score</span>
                  <ScorePill score={data.epfo.stability_score} />
                </div>
              </Section>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
