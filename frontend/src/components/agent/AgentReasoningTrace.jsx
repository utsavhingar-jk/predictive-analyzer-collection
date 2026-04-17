/**
 * AgentReasoningTrace
 *
 * Premium visual display of GPT-4o's ReAct loop tool calls.
 * Shows each step with: thought, tool called, key outputs, and raw I/O.
 */

import { useState } from "react";
import {
  Brain, Wrench, ChevronDown, ChevronRight,
  CheckCircle2, Sparkles, Zap, TrendingUp,
  Shield, Users, FileText, BarChart3,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// ─── Tool configuration ───────────────────────────────────────────────────────

const TOOL_CONFIG = {
  analyze_payment_behavior: {
    label: "Payment Behavior Analysis",
    shortLabel: "Behavior",
    icon: Brain,
    gradient: "from-purple-500/10 to-purple-500/5",
    border: "border-purple-400/30",
    dot: "bg-purple-500",
    badge: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300 border-purple-200 dark:border-purple-800",
    icon_color: "text-purple-500",
    bar_color: "bg-purple-500",
  },
  predict_invoice_delay: {
    label: "Delay Risk Prediction",
    shortLabel: "Delay",
    icon: TrendingUp,
    gradient: "from-red-500/10 to-red-500/5",
    border: "border-red-400/30",
    dot: "bg-red-500",
    badge: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300 border-red-200 dark:border-red-800",
    icon_color: "text-red-500",
    bar_color: "bg-red-500",
  },
  optimize_collection_strategy: {
    label: "Collection Strategy",
    shortLabel: "Strategy",
    icon: Zap,
    gradient: "from-blue-500/10 to-blue-500/5",
    border: "border-blue-400/30",
    dot: "bg-blue-500",
    badge: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 border-blue-200 dark:border-blue-800",
    icon_color: "text-blue-500",
    bar_color: "bg-blue-500",
  },
  get_borrower_risk: {
    label: "Borrower Risk Profile",
    shortLabel: "Borrower",
    icon: Users,
    gradient: "from-amber-500/10 to-amber-500/5",
    border: "border-amber-400/30",
    dot: "bg-amber-500",
    badge: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300 border-amber-200 dark:border-amber-800",
    icon_color: "text-amber-500",
    bar_color: "bg-amber-500",
  },
  get_invoice_details: {
    label: "Invoice Details",
    shortLabel: "Invoice",
    icon: FileText,
    gradient: "from-green-500/10 to-green-500/5",
    border: "border-green-400/30",
    dot: "bg-green-500",
    badge: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300 border-green-200 dark:border-green-800",
    icon_color: "text-green-500",
    bar_color: "bg-green-500",
  },
  get_portfolio_summary: {
    label: "Portfolio Summary",
    shortLabel: "Portfolio",
    icon: BarChart3,
    gradient: "from-teal-500/10 to-teal-500/5",
    border: "border-teal-400/30",
    dot: "bg-teal-500",
    badge: "bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-300 border-teal-200 dark:border-teal-800",
    icon_color: "text-teal-500",
    bar_color: "bg-teal-500",
  },
  get_portfolio_worklist: {
    label: "Escalation Worklist",
    shortLabel: "Worklist",
    icon: BarChart3,
    gradient: "from-cyan-500/10 to-cyan-500/5",
    border: "border-cyan-400/30",
    dot: "bg-cyan-500",
    badge: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300 border-cyan-200 dark:border-cyan-800",
    icon_color: "text-cyan-500",
    bar_color: "bg-cyan-500",
  },
};

const DEFAULT_CONFIG = {
  label: "Tool Called",
  shortLabel: "Tool",
  icon: Wrench,
  gradient: "from-muted/20 to-muted/10",
  border: "border-border",
  dot: "bg-muted-foreground",
  badge: "bg-muted text-muted-foreground border-border",
  icon_color: "text-muted-foreground",
  bar_color: "bg-muted-foreground",
};

// ─── Key metric extraction per tool ──────────────────────────────────────────

function extractMetrics(toolName, output) {
  if (!output || output.error) return [];
  const fmt = (n) => typeof n === "number" ? new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n) : n;

  if (toolName === "analyze_payment_behavior") return [
    output.behavior_type && ["Behavior", output.behavior_type],
    output.on_time_ratio !== undefined && ["On-Time", `${output.on_time_ratio}%`],
    output.trend && ["Trend", output.trend],
    output.behavior_risk_score !== undefined && ["Risk Score", `${output.behavior_risk_score}/100`],
    output.nach_recommended !== undefined && ["NACH", output.nach_recommended ? "Recommended" : "Not needed"],
  ].filter(Boolean);

  if (toolName === "predict_invoice_delay") return [
    output.delay_probability !== undefined && ["Delay Prob.", `${(output.delay_probability * 100).toFixed(0)}%`],
    output.risk_tier && ["Risk Tier", output.risk_tier],
    output.risk_score !== undefined && ["Risk Score", `${output.risk_score}/100`],
    output.top_drivers?.length && ["Top Driver", output.top_drivers[0]],
  ].filter(Boolean);

  if (toolName === "optimize_collection_strategy") return [
    output.recommended_action && ["Action", output.recommended_action],
    output.urgency && ["Urgency", output.urgency],
    output.priority_score !== undefined && ["Priority", `${output.priority_score}/100`],
    output.next_action_in_hours !== undefined && ["SLA", `${output.next_action_in_hours}h`],
  ].filter(Boolean);

  if (toolName === "get_borrower_risk") return [
    output.borrower_risk_tier && ["Risk Tier", output.borrower_risk_tier],
    output.borrower_risk_score !== undefined && ["Score", `${output.borrower_risk_score}/100`],
    output.total_outstanding !== undefined && ["Outstanding", fmt(output.total_outstanding)],
    output.escalation_recommended !== undefined && ["Escalate", output.escalation_recommended ? "Yes" : "No"],
  ].filter(Boolean);

  if (toolName === "get_invoice_details") return [
    output.customer_name && ["Customer", output.customer_name],
    output.amount !== undefined && ["Amount", fmt(output.amount)],
    output.status && ["Status", output.status?.toUpperCase()],
    output.days_overdue !== undefined && ["DPD", `${output.days_overdue} days`],
  ].filter(Boolean);

  if (toolName === "get_portfolio_summary") return [
    output.total_outstanding !== undefined && ["Outstanding", fmt(output.total_outstanding)],
    output.high_risk_count !== undefined && ["High Risk", output.high_risk_count],
    output.amount_at_risk !== undefined && ["At Risk", fmt(output.amount_at_risk)],
    output.total_invoices !== undefined && ["Invoices", output.total_invoices],
  ].filter(Boolean);

  return [];
}

// ─── Single step card ─────────────────────────────────────────────────────────

function TraceStep({ step, index, isLast }) {
  const [expanded, setExpanded] = useState(false);
  const cfg = TOOL_CONFIG[step.tool_name] || DEFAULT_CONFIG;
  const Icon = cfg.icon;
  const metrics = extractMetrics(step.tool_name, step.tool_output);

  return (
    <div className="flex gap-3">
      {/* Timeline spine */}
      <div className="flex flex-col items-center pt-1 shrink-0">
        <div className={`w-7 h-7 rounded-full ${cfg.dot} bg-opacity-20 border-2 border-current flex items-center justify-center text-white text-xs font-bold shrink-0`}
             style={{ borderColor: "currentColor" }}>
          <span className={cfg.icon_color + " font-bold text-xs"}>{index + 1}</span>
        </div>
        {!isLast && <div className="w-px flex-1 bg-gradient-to-b from-border to-transparent mt-2 min-h-[24px]" />}
      </div>

      {/* Step card */}
      <div className={`flex-1 mb-4 rounded-xl border bg-gradient-to-br ${cfg.gradient} ${cfg.border} overflow-hidden`}>
        {/* Card header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
          <div className="flex items-center gap-2.5">
            <div className={`w-7 h-7 rounded-lg bg-background/80 border ${cfg.border} flex items-center justify-center`}>
              <Icon className={`h-3.5 w-3.5 ${cfg.icon_color}`} />
            </div>
            <div>
              <p className={`text-sm font-semibold ${cfg.icon_color}`}>{cfg.label}</p>
              <p className="text-xs text-muted-foreground font-mono">{step.tool_name}</p>
            </div>
          </div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded hover:bg-background/50"
            title={expanded ? "Hide raw I/O" : "Show raw I/O"}
          >
            {expanded
              ? <ChevronDown className="h-4 w-4" />
              : <ChevronRight className="h-4 w-4" />}
          </button>
        </div>

        <div className="px-4 py-3 space-y-3">
          {/* Agent thought bubble */}
          {step.agent_thought && (
            <div className="flex items-start gap-2 p-2.5 rounded-lg bg-background/60 border border-border/40">
              <Brain className="h-3.5 w-3.5 text-muted-foreground mt-0.5 shrink-0" />
              <p className="text-xs text-muted-foreground italic leading-relaxed">
                {step.agent_thought}
              </p>
            </div>
          )}

          {/* Key metrics grid */}
          {metrics.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {metrics.map(([label, value]) => (
                <div key={label} className="p-2 rounded-lg bg-background/70 border border-border/40 text-center">
                  <p className="text-xs text-muted-foreground mb-0.5">{label}</p>
                  <p className="text-xs font-bold text-foreground leading-tight break-words">{String(value)}</p>
                </div>
              ))}
            </div>
          )}

          {/* Expandable raw I/O */}
          {expanded && (
            <div className="space-y-2 pt-1">
              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Input</p>
                <pre className="text-xs bg-background rounded-lg p-3 overflow-x-auto text-foreground/80 border border-border leading-relaxed max-h-40 scrollbar-thin">
                  {JSON.stringify(step.tool_input, null, 2)}
                </pre>
              </div>
              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Output</p>
                <pre className="text-xs bg-background rounded-lg p-3 overflow-x-auto text-foreground/80 border border-border leading-relaxed max-h-48 scrollbar-thin">
                  {JSON.stringify(step.tool_output, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function AgentReasoningTrace({ trace = [], iterations = 0, toolsCalled = [], summary = "" }) {
  const [open, setOpen] = useState(true);

  if (!trace || trace.length === 0) return null;

  return (
    <Card className="border-primary/25 overflow-hidden">
      {/* Gradient header */}
      <CardHeader className="bg-gradient-to-r from-primary/10 via-primary/5 to-background border-b border-primary/20 pb-3">
        <CardTitle className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-primary/15 border border-primary/30 flex items-center justify-center">
              <Sparkles className="h-4 w-4 text-primary" />
            </div>
            <div>
              <p className="text-sm font-bold text-foreground">GPT-4o Agent Reasoning</p>
              <p className="text-xs text-muted-foreground">ReAct loop — autonomous tool orchestration</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Stats pills */}
            <div className="flex items-center gap-1.5 text-xs">
              <span className="flex items-center gap-1 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 border border-green-200 dark:border-green-800 px-2 py-0.5 rounded-full font-medium">
                <CheckCircle2 className="h-3 w-3" />
                {trace.length} tool{trace.length !== 1 ? "s" : ""}
              </span>
              <span className="flex items-center gap-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800 px-2 py-0.5 rounded-full font-medium">
                <Zap className="h-3 w-3" />
                {iterations} iteration{iterations !== 1 ? "s" : ""}
              </span>
            </div>
            <button
              onClick={() => setOpen(!open)}
              className="text-xs text-primary hover:text-primary/80 font-medium transition-colors px-2 py-0.5 rounded border border-primary/20 hover:bg-primary/10"
            >
              {open ? "Collapse" : "Expand"}
            </button>
          </div>
        </CardTitle>
      </CardHeader>

      {open && (
        <CardContent className="pt-5">
          {/* Tool pipeline pills */}
          <div className="flex flex-wrap items-center gap-2 mb-5 p-3 rounded-xl bg-muted/30 border border-border">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Pipeline:</span>
            {toolsCalled.map((name, i) => {
              const cfg = TOOL_CONFIG[name] || DEFAULT_CONFIG;
              const CfgIcon = cfg.icon;
              return (
                <span key={i} className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border font-medium ${cfg.badge}`}>
                  <CfgIcon className="h-3 w-3" />
                  {cfg.shortLabel}
                  {i < toolsCalled.length - 1 && (
                    <ChevronRight className="h-3 w-3 opacity-50 ml-0.5" />
                  )}
                </span>
              );
            })}
          </div>

          {/* Trace timeline */}
          <div>
            {trace.map((step, idx) => (
              <TraceStep
                key={step.step ?? idx}
                step={step}
                index={idx}
                isLast={idx === trace.length - 1}
              />
            ))}
          </div>

          {/* Final synthesis */}
          {summary && (
            <div className="mt-2 rounded-xl border border-primary/25 bg-gradient-to-br from-primary/10 to-primary/5 p-4">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-6 h-6 rounded-lg bg-primary/20 flex items-center justify-center">
                  <Shield className="h-3.5 w-3.5 text-primary" />
                </div>
                <span className="text-xs font-bold text-primary uppercase tracking-wide">GPT-4o Final Analysis</span>
              </div>
              <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">{summary}</p>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
