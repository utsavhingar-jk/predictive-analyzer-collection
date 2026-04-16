/**
 * InteractionTimeline — shows collections interaction history as a vertical timeline.
 * Displays every touchpoint: calls, emails, legal notices, PTPs, field visits.
 */

import { useState, useEffect } from "react";
import {
  Phone, Mail, FileText, Users, CheckCircle2, XCircle,
  AlertTriangle, Clock, Banknote, ChevronDown, ChevronRight,
  History, TrendingUp,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

// ── Outcome metadata ──────────────────────────────────────────────────────────

const OUTCOME_META = {
  collected_full:    { label: "Fully Collected",   icon: CheckCircle2, color: "text-green-600 dark:text-green-400",  dot: "bg-green-500" },
  collected_partial: { label: "Partial Payment",   icon: Banknote,     color: "text-teal-600 dark:text-teal-400",    dot: "bg-teal-500" },
  ptp_given:         { label: "PTP Given",          icon: Clock,        color: "text-blue-600 dark:text-blue-400",    dot: "bg-blue-500" },
  broken_ptp:        { label: "PTP Broken",         icon: XCircle,      color: "text-red-600 dark:text-red-400",      dot: "bg-red-500" },
  no_answer:         { label: "No Answer",          icon: Phone,        color: "text-muted-foreground",               dot: "bg-muted-foreground" },
  refused:           { label: "Refused",            icon: XCircle,      color: "text-orange-600 dark:text-orange-400",dot: "bg-orange-500" },
  dispute_raised:    { label: "Dispute Raised",     icon: AlertTriangle,color: "text-amber-600 dark:text-amber-400",  dot: "bg-amber-500" },
  no_response:       { label: "No Response",        icon: Mail,         color: "text-muted-foreground",               dot: "bg-muted-foreground" },
  escalated:         { label: "Escalated",          icon: AlertTriangle,color: "text-red-600 dark:text-red-400",      dot: "bg-red-500" },
};

const ACTION_ICON = {
  "Call":          Phone,
  "Email":         Mail,
  "Legal Notice":  FileText,
  "Field Visit":   Users,
  "NACH Trigger":  Banknote,
  "Payment Plan":  TrendingUp,
  "WhatsApp":      Mail,
};

const OUTCOME_BG = {
  collected_full:    "bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800",
  collected_partial: "bg-teal-50 border-teal-200 dark:bg-teal-900/20 dark:border-teal-800",
  ptp_given:         "bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-800",
  broken_ptp:        "bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800",
  dispute_raised:    "bg-amber-50 border-amber-200 dark:bg-amber-900/20 dark:border-amber-800",
  refused:           "bg-orange-50 border-orange-200 dark:bg-orange-900/20 dark:border-orange-800",
  escalated:         "bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800",
};

function TimelineItem({ interaction, isLast }) {
  const outcome = OUTCOME_META[interaction.outcome] || { label: interaction.outcome, icon: Clock, color: "text-muted-foreground", dot: "bg-muted-foreground" };
  const OutcomeIcon = outcome.icon;
  const ActionIcon = ACTION_ICON[interaction.action_type] || Phone;
  const bg = OUTCOME_BG[interaction.outcome] || "bg-muted/30 border-border";

  return (
    <div className="flex gap-3">
      {/* Timeline line */}
      <div className="flex flex-col items-center">
        <div className={`w-7 h-7 rounded-full border-2 border-background flex items-center justify-center shrink-0 z-10 ${
          ["collected_full", "collected_partial"].includes(interaction.outcome) ? "bg-green-500"
          : ["broken_ptp", "refused", "escalated"].includes(interaction.outcome) ? "bg-red-500"
          : interaction.outcome === "ptp_given" ? "bg-blue-500"
          : "bg-muted"
        }`}>
          <ActionIcon className="h-3 w-3 text-white" />
        </div>
        {!isLast && <div className="w-0.5 h-full bg-border mt-1 mb-0" />}
      </div>

      {/* Content */}
      <div className={`flex-1 mb-3 rounded-lg border p-3 ${bg}`}>
        <div className="flex items-start justify-between gap-2 mb-1">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-semibold text-foreground">{interaction.action_type}</span>
              <span className={`inline-flex items-center gap-1 text-xs font-medium ${outcome.color}`}>
                <OutcomeIcon className="h-3 w-3" />
                {outcome.label}
              </span>
              {interaction.broken_ptp && (
                <span className="text-xs px-1.5 py-0.5 rounded bg-red-100 text-red-700 border border-red-200 dark:bg-red-900/40 dark:text-red-300 dark:border-red-800">
                  Broken PTP
                </span>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              {interaction.date}
              {interaction.collector_name && ` · ${interaction.collector_name}`}
            </p>
          </div>
          {interaction.amount_recovered && (
            <span className="text-xs font-bold text-green-700 dark:text-green-400 shrink-0">
              +{formatCurrency(interaction.amount_recovered)}
            </span>
          )}
        </div>

        {interaction.notes && (
          <p className="text-xs text-foreground/70 mt-1 leading-relaxed">{interaction.notes}</p>
        )}

        {interaction.ptp_amount && !interaction.broken_ptp && (
          <div className="mt-1.5 flex items-center gap-2 text-xs text-blue-700 dark:text-blue-300">
            <Clock className="h-3 w-3" />
            <span>PTP: {formatCurrency(interaction.ptp_amount)} by {interaction.ptp_date}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export function InteractionTimeline({ invoiceId }) {
  const [data, setData] = useState(null);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    if (!invoiceId) return;
    api.getInteractions(invoiceId).then(setData).catch(() => {});
  }, [invoiceId]);

  if (!data || data.total_interactions === 0) return null;

  const interactions = data.interactions || [];
  const visible = showAll ? interactions : interactions.slice(-3);

  return (
    <Card className="border-border">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <History className="h-4 w-4 text-primary" />
          Interaction History
          <span className="text-xs font-normal text-muted-foreground">
            · {data.total_interactions} touchpoints
          </span>
          {data.total_recovered > 0 && (
            <span className="ml-auto text-xs font-semibold text-green-700 dark:text-green-400">
              {formatCurrency(data.total_recovered)} recovered
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-1">
        {/* Summary strip */}
        <div className="flex items-center gap-3 mb-3 p-2 rounded-lg bg-muted/30 text-xs flex-wrap">
          {data.has_broken_ptp && (
            <span className="flex items-center gap-1 text-red-600 dark:text-red-400 font-medium">
              <XCircle className="h-3 w-3" /> Broken PTP recorded
            </span>
          )}
          {data.open_ptp_amount && (
            <span className="flex items-center gap-1 text-blue-600 dark:text-blue-400 font-medium">
              <Clock className="h-3 w-3" /> Open PTP: {formatCurrency(data.open_ptp_amount)}
            </span>
          )}
          <span className="flex items-center gap-1 text-primary font-medium ml-auto">
            <TrendingUp className="h-3 w-3" />
            History-recommended: <strong className="ml-0.5">{data.best_action}</strong>
          </span>
        </div>

        {/* Timeline */}
        {interactions.length > 3 && !showAll && (
          <button
            onClick={() => setShowAll(true)}
            className="w-full text-xs text-muted-foreground hover:text-foreground py-1 mb-2 flex items-center justify-center gap-1 transition-colors"
          >
            <ChevronRight className="h-3 w-3" /> Show {interactions.length - 3} earlier interactions
          </button>
        )}

        <div>
          {visible.map((i, idx) => (
            <TimelineItem key={i.interaction_id} interaction={i} isLast={idx === visible.length - 1} />
          ))}
        </div>

        {showAll && (
          <button
            onClick={() => setShowAll(false)}
            className="w-full text-xs text-muted-foreground hover:text-foreground py-1 flex items-center justify-center gap-1 transition-colors"
          >
            <ChevronDown className="h-3 w-3" /> Collapse
          </button>
        )}

        {/* Confidence boost */}
        {data.learning_confidence_boost > 0 && (
          <div className="mt-2 pt-2 border-t border-border flex items-center gap-2">
            <div className="text-xs text-muted-foreground">
              History enrichment: prediction confidence
              <span className="text-green-600 dark:text-green-400 font-semibold ml-1">
                +{Math.round(data.learning_confidence_boost * 100)}%
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
