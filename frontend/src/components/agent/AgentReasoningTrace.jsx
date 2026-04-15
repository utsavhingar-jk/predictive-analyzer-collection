/**
 * AgentReasoningTrace
 *
 * Renders the step-by-step tool calls GPT-4o made during its ReAct loop.
 * Shows: tool name, inputs, outputs, and GPT's thought before each call.
 */

import { useState } from "react";
import {
  Brain,
  Wrench,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Sparkles,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const TOOL_META = {
  analyze_payment_behavior: {
    label: "Analyzed Payment Behavior",
    color: "text-purple-600 dark:text-purple-400",
    bg: "bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800",
    dot: "bg-purple-500",
  },
  predict_invoice_delay: {
    label: "Predicted Invoice Delay",
    color: "text-red-600 dark:text-red-400",
    bg: "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800",
    dot: "bg-red-500",
  },
  optimize_collection_strategy: {
    label: "Optimized Collection Strategy",
    color: "text-blue-600 dark:text-blue-400",
    bg: "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800",
    dot: "bg-blue-500",
  },
  get_borrower_risk: {
    label: "Fetched Borrower Risk",
    color: "text-amber-600 dark:text-amber-400",
    bg: "bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800",
    dot: "bg-amber-500",
  },
  get_invoice_details: {
    label: "Retrieved Invoice Details",
    color: "text-green-600 dark:text-green-400",
    bg: "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800",
    dot: "bg-green-500",
  },
  get_portfolio_summary: {
    label: "Checked Portfolio Summary",
    color: "text-teal-600 dark:text-teal-400",
    bg: "bg-teal-50 dark:bg-teal-900/20 border-teal-200 dark:border-teal-800",
    dot: "bg-teal-500",
  },
};

const DEFAULT_META = {
  label: "Called Tool",
  color: "text-muted-foreground",
  bg: "bg-muted/50 border-border",
  dot: "bg-muted-foreground",
};

function KeyOutputs({ toolName, output }) {
  if (!output || output.error) return null;

  const rows = [];

  if (toolName === "analyze_payment_behavior") {
    if (output.behavior_type) rows.push(["Behavior Type", output.behavior_type]);
    if (output.on_time_ratio !== undefined) rows.push(["On-Time Ratio", `${output.on_time_ratio}%`]);
    if (output.trend) rows.push(["Trend", output.trend]);
    if (output.behavior_risk_score !== undefined) rows.push(["Risk Score", `${output.behavior_risk_score}/100`]);
    if (output.nach_recommended !== undefined) rows.push(["NACH Recommended", output.nach_recommended ? "Yes" : "No"]);
  } else if (toolName === "predict_invoice_delay") {
    if (output.delay_probability !== undefined) rows.push(["Delay Probability", `${(output.delay_probability * 100).toFixed(0)}%`]);
    if (output.risk_tier) rows.push(["Risk Tier", output.risk_tier]);
    if (output.risk_score !== undefined) rows.push(["Risk Score", `${output.risk_score}/100`]);
    if (output.top_drivers?.length) rows.push(["Top Drivers", output.top_drivers.slice(0, 2).join("; ")]);
  } else if (toolName === "optimize_collection_strategy") {
    if (output.recommended_action) rows.push(["Action", output.recommended_action]);
    if (output.urgency) rows.push(["Urgency", output.urgency]);
    if (output.priority_score !== undefined) rows.push(["Priority Score", `${output.priority_score}/100`]);
    if (output.next_action_in_hours !== undefined) rows.push(["SLA", `${output.next_action_in_hours}h`]);
  } else if (toolName === "get_borrower_risk") {
    if (output.borrower_risk_tier) rows.push(["Risk Tier", output.borrower_risk_tier]);
    if (output.borrower_risk_score !== undefined) rows.push(["Risk Score", `${output.borrower_risk_score}/100`]);
    if (output.total_outstanding !== undefined) rows.push(["Outstanding", `$${output.total_outstanding.toLocaleString()}`]);
    if (output.escalation_recommended !== undefined) rows.push(["Escalate", output.escalation_recommended ? "Yes" : "No"]);
  } else if (toolName === "get_invoice_details") {
    if (output.customer_name) rows.push(["Customer", output.customer_name]);
    if (output.amount !== undefined) rows.push(["Amount", `$${output.amount.toLocaleString()}`]);
    if (output.status) rows.push(["Status", output.status]);
    if (output.days_overdue !== undefined) rows.push(["Days Overdue", output.days_overdue]);
  } else if (toolName === "get_portfolio_summary") {
    if (output.total_outstanding !== undefined) rows.push(["Total Outstanding", `$${output.total_outstanding.toLocaleString()}`]);
    if (output.high_risk_count !== undefined) rows.push(["High Risk", output.high_risk_count]);
    if (output.amount_at_risk !== undefined) rows.push(["At Risk", `$${output.amount_at_risk.toLocaleString()}`]);
  }

  if (!rows.length) return null;

  return (
    <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1">
      {rows.map(([label, value]) => (
        <div key={label} className="flex items-center gap-1.5 text-xs">
          <span className="text-muted-foreground">{label}:</span>
          <span className="font-semibold text-foreground">{String(value)}</span>
        </div>
      ))}
    </div>
  );
}

function TraceStep({ step, isLast }) {
  const [expanded, setExpanded] = useState(false);
  const meta = TOOL_META[step.tool_name] || DEFAULT_META;

  return (
    <div className="flex gap-3">
      {/* Timeline line */}
      <div className="flex flex-col items-center">
        <div className={`w-2.5 h-2.5 rounded-full mt-1 shrink-0 ${meta.dot}`} />
        {!isLast && <div className="w-px flex-1 bg-border mt-1" />}
      </div>

      {/* Step content */}
      <div className={`flex-1 rounded-lg border p-3 mb-3 ${meta.bg}`}>
        {/* Header row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Wrench className={`h-3.5 w-3.5 ${meta.color}`} />
            <span className={`text-xs font-semibold ${meta.color}`}>{meta.label}</span>
            <span className="text-xs text-muted-foreground bg-background/60 px-1.5 py-0.5 rounded font-mono">
              {step.tool_name}
            </span>
          </div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            {expanded
              ? <ChevronDown className="h-3.5 w-3.5" />
              : <ChevronRight className="h-3.5 w-3.5" />
            }
          </button>
        </div>

        {/* GPT's thought before this tool call */}
        {step.agent_thought && (
          <div className="mt-2 flex items-start gap-1.5">
            <Brain className="h-3 w-3 text-muted-foreground mt-0.5 shrink-0" />
            <p className="text-xs text-muted-foreground italic leading-relaxed">
              {step.agent_thought}
            </p>
          </div>
        )}

        {/* Key outputs summary */}
        <KeyOutputs toolName={step.tool_name} output={step.tool_output} />

        {/* Expandable raw I/O */}
        {expanded && (
          <div className="mt-3 space-y-2">
            <div>
              <p className="text-xs font-semibold text-muted-foreground mb-1">Input</p>
              <pre className="text-xs bg-background/80 rounded p-2 overflow-x-auto text-foreground leading-relaxed">
                {JSON.stringify(step.tool_input, null, 2)}
              </pre>
            </div>
            <div>
              <p className="text-xs font-semibold text-muted-foreground mb-1">Output</p>
              <pre className="text-xs bg-background/80 rounded p-2 overflow-x-auto text-foreground leading-relaxed max-h-48">
                {JSON.stringify(step.tool_output, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function AgentReasoningTrace({ trace = [], iterations = 0, toolsCalled = [], summary = "" }) {
  const [open, setOpen] = useState(true);

  if (!trace || trace.length === 0) return null;

  return (
    <Card className="border-primary/30">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            Agent Reasoning Trace
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
              {trace.length} tool call{trace.length !== 1 ? "s" : ""} · {iterations} iteration{iterations !== 1 ? "s" : ""}
            </div>
            <button
              onClick={() => setOpen(!open)}
              className="text-xs text-primary hover:underline"
            >
              {open ? "Collapse" : "Expand"}
            </button>
          </div>
        </CardTitle>
      </CardHeader>

      {open && (
        <CardContent>
          {/* Tool pills */}
          <div className="flex flex-wrap gap-1.5 mb-4">
            {toolsCalled.map((name, i) => {
              const meta = TOOL_META[name] || DEFAULT_META;
              return (
                <span
                  key={i}
                  className={`text-xs px-2 py-0.5 rounded-full border font-medium ${meta.color} ${meta.bg}`}
                >
                  {i + 1}. {(TOOL_META[name]?.label || name).replace("Called ", "")}
                </span>
              );
            })}
          </div>

          {/* Timeline */}
          <div>
            {trace.map((step, idx) => (
              <TraceStep
                key={step.step}
                step={step}
                isLast={idx === trace.length - 1}
              />
            ))}
          </div>

          {/* Final summary */}
          {summary && (
            <div className="mt-1 p-3 rounded-lg bg-primary/10 border border-primary/20">
              <div className="flex items-center gap-1.5 mb-1.5">
                <Brain className="h-3.5 w-3.5 text-primary" />
                <span className="text-xs font-semibold text-primary">Agent Final Analysis</span>
              </div>
              <p className="text-sm text-foreground leading-relaxed">{summary}</p>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
